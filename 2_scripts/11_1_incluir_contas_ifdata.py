# incluir_contas_ifdata.py

import argparse
import glob
import re
import unicodedata
from pathlib import Path

import pandas as pd


# Mapeamento principal das contas nos relatórios IFData
# Relatório 2 = Ativo
# Relatório 3 = Passivo
# Relatório 4 = Demonstração de Resultado
# python 11_1_incluir_contas_ifdata.py --base bases/base_com_contas.xlsx --relatorios ifdata/extracted/ext_202412_t1_r2.csv ifdata/extracted/ext_202412_t1_r3.csv ifdata/extracted/ext_202412_t1_r4.csv --saida bases/base_com_contas.xlsx
ACCOUNT_MAP = {
    ("2", "78182"): "ativo_total",
    ("2", "78188"): "disponibilidades",
    ("2", "78201"): "permanente_ajustado",

    ("3", "78186"): "patrimonio_liquido",
    ("3", "78298"): "passivo_circulante_e_exigivel_a_longo_prazo",
    ("3", "78300"): "passivo_total",

    ("4", "78187"): "lucro_liquido",
}

TARGET_COLS = [
    "ativo_total",
    "disponibilidades",
    "permanente_ajustado",
    "patrimonio_liquido",
    "passivo_circulante_e_exigivel_a_longo_prazo",
    "passivo_total",
    "lucro_liquido",
]


# Candidatos de CodInst para compatibilizar ticker / código prudencial / código de conglomerado.
# O script também funciona com arquivo externo de mapeamento, via --mapa_codinst.
DEFAULT_ID_CANDIDATES = {
    "ABCB4": ["C0041856", "C0080312"],
    "BAZA3": ["C0081249"],
    "BBAS3": ["C0049906", "C0080329"],
    "BBDC4": ["C0010045", "C0080075"],
    "BEES4": ["C0030159", "C0080147"],
    "BGIP4": ["C0081634"],
    "BNBR3": ["C0081593"],
    "BRSR5": ["C0030173", "C0080154"],
    "BRSR6": ["C0030173", "C0080154"],
    "BSLI3": ["C0080288"],
    "BSLI4": ["C0080288", "C0031976"],
    "PINE4": ["C0080374"],
    "RPAD5": ["C0010083", "C0080109"],
    "RPAD6": ["C0010083", "C0080109"],
    "SANB3": ["C0030379", "C0080185"],
    "SANB4": ["C0030379", "C0080185"],
    "SANB11": ["C0030379", "C0080185"],
    "BPAC11": ["C0049944", "C0080336"],

    # Códigos prudenciais presentes na base que podem aparecer como conglomerado nos relatórios.
    "C0080123": ["C0020152", "C0080123"],
    "C0080336": ["C0049944", "C0080336"],
}


def normalize_text(value: object) -> str:
    """Normaliza texto para comparação: minúsculo, sem acentos e sem excesso de espaços."""
    if pd.isna(value):
        return ""
    text = str(value).replace("\n", " ").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text)
    return text


def parse_number_br(value: object) -> float:
    """Converte número em formato BR ou internacional para float."""
    if pd.isna(value):
        return pd.NA

    s = str(value).strip()
    if s == "":
        return pd.NA

    # Remove espaços e separadores não numéricos preservando sinal, vírgula e ponto
    s = re.sub(r"[^\d,.\-]", "", s)

    # Caso BR: 1.234.567,89
    if "," in s and "." in s and s.rfind(",") > s.rfind("."):
        s = s.replace(".", "").replace(",", ".")
    # Caso com vírgula decimal: 1234,89
    elif "," in s and "." not in s:
        s = s.replace(",", ".")

    return pd.to_numeric(s, errors="coerce")


def read_base(base_path: str, sheet_name: str | int | None = 0) -> pd.DataFrame:
    df = pd.read_excel(base_path, sheet_name=sheet_name, dtype={"AnoMes_ord": str, "id_entidade": str})

    required = {"AnoMes_ord", "id_entidade"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"A base precisa conter as colunas {required}. Ausentes: {missing}")

    df["AnoMes_ord"] = df["AnoMes_ord"].astype(str).str.extract(r"(\d{6})", expand=False)
    df["id_entidade"] = df["id_entidade"].astype(str).str.strip()

    # Corrige a grafia da coluna, sem apagar a coluna antiga.
    if "disponilidades" in df.columns and "disponibilidades" not in df.columns:
        df["disponibilidades"] = df["disponilidades"]

    for col in TARGET_COLS:
        if col not in df.columns:
            df[col] = pd.NA

    return df


def expand_report_paths(paths: list[str]) -> list[str]:
    files = []
    for item in paths:
        matches = glob.glob(item)
        if matches:
            files.extend(matches)
        else:
            files.append(item)

    files = sorted(set(files))
    missing = [f for f in files if not Path(f).exists()]
    if missing:
        raise FileNotFoundError(f"Arquivos não encontrados: {missing}")

    return files


def identify_account(row: pd.Series) -> str | None:
    """Identifica a conta desejada por NumeroRelatorio + Conta; usa NomeColuna como fallback."""
    numero = str(row.get("NumeroRelatorio", "")).strip()
    conta = str(row.get("Conta", "")).strip()

    if (numero, conta) in ACCOUNT_MAP:
        return ACCOUNT_MAP[(numero, conta)]

    nome = normalize_text(row.get("NomeColuna", ""))

    fallback_names = {
        "ativo total": "ativo_total",
        "disponibilidades": "disponibilidades",
        "permanente ajustado": "permanente_ajustado",
        "patrimonio liquido": "patrimonio_liquido",
        "passivo circulante e exigivel a longo prazo": "passivo_circulante_e_exigivel_a_longo_prazo",
        "passivo total": "passivo_total",
        "lucro liquido": "lucro_liquido",
    }

    for key, target in fallback_names.items():
        if nome.startswith(key):
            return target

    return None


def read_reports(report_paths: list[str]) -> pd.DataFrame:
    all_rows = []

    for path in report_paths:
        df = pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig", dtype=str)

        required = {"CodInst", "AnoMes", "Saldo"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"O relatório {path} não contém as colunas obrigatórias: {missing}")

        df["target_col"] = df.apply(identify_account, axis=1)
        df = df[df["target_col"].notna()].copy()

        if df.empty:
            print(f"[aviso] Nenhuma das contas-alvo foi encontrada em: {path}")
            continue

        df["AnoMes"] = df["AnoMes"].astype(str).str.extract(r"(\d{6})", expand=False)
        df["CodInst"] = df["CodInst"].astype(str).str.strip()
        df["Saldo"] = df["Saldo"].apply(parse_number_br)

        all_rows.append(df[["AnoMes", "CodInst", "target_col", "Saldo"]])

    if not all_rows:
        raise ValueError("Nenhuma conta-alvo foi encontrada nos relatórios informados.")

    long_df = pd.concat(all_rows, ignore_index=True)

    # Se houver duplicatas para a mesma conta/chave, mantém a última ocorrência.
    long_df = long_df.drop_duplicates(
        subset=["AnoMes", "CodInst", "target_col"],
        keep="last"
    )

    pivot = (
        long_df
        .pivot_table(
            index=["AnoMes", "CodInst"],
            columns="target_col",
            values="Saldo",
            aggfunc="last"
        )
        .reset_index()
    )

    return pivot


def load_external_mapping(path: str | None) -> dict[str, list[str]]:
    """
    Arquivo opcional com colunas:
    id_entidade,CodInst

    Permite vários CodInst para o mesmo id_entidade.
    """
    mapping = {k: list(v) for k, v in DEFAULT_ID_CANDIDATES.items()}

    if path is None:
        return mapping

    map_df = pd.read_csv(path, dtype=str)
    required = {"id_entidade", "CodInst"}
    missing = required - set(map_df.columns)
    if missing:
        raise ValueError(f"O mapa precisa conter as colunas {required}. Ausentes: {missing}")

    for _, row in map_df.iterrows():
        key = str(row["id_entidade"]).strip()
        cod = str(row["CodInst"]).strip()
        if key and cod:
            mapping.setdefault(key, [])
            if cod not in mapping[key]:
                mapping[key].append(cod)

    return mapping


def candidate_codes(id_entidade: str, mapping: dict[str, list[str]], report_codes: set[str]) -> list[str]:
    """
    Gera candidatos de CodInst.
    Prioriza correspondência direta quando o id_entidade já aparece no relatório.
    """
    id_entidade = str(id_entidade).strip()
    candidates = []

    if id_entidade in report_codes:
        candidates.append(id_entidade)

    for cod in mapping.get(id_entidade, []):
        if cod not in candidates:
            candidates.append(cod)

    if id_entidade not in candidates:
        candidates.append(id_entidade)

    return candidates


def merge_accounts(
    base_df: pd.DataFrame,
    report_df: pd.DataFrame,
    mapping: dict[str, list[str]],
    overwrite: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = base_df.copy()
    base["_row_id"] = range(len(base))

    report_codes = set(report_df["CodInst"].astype(str))

    exploded_rows = []
    for _, row in base[["_row_id", "AnoMes_ord", "id_entidade"]].iterrows():
        codes = candidate_codes(row["id_entidade"], mapping, report_codes)
        for priority, cod in enumerate(codes):
            exploded_rows.append({
                "_row_id": row["_row_id"],
                "AnoMes": row["AnoMes_ord"],
                "CodInst": cod,
                "_priority": priority,
            })

    candidates_df = pd.DataFrame(exploded_rows)

    merged = candidates_df.merge(
        report_df,
        how="left",
        on=["AnoMes", "CodInst"]
    )

    account_cols = [c for c in TARGET_COLS if c in merged.columns]
    merged["_has_match"] = merged[account_cols].notna().any(axis=1)

    best = (
        merged[merged["_has_match"]]
        .sort_values(["_row_id", "_priority"])
        .drop_duplicates("_row_id", keep="first")
        .set_index("_row_id")
    )

    fill_report = []

    for col in TARGET_COLS:
        if col not in best.columns:
            continue

        values = best[col]
        idx = values.dropna().index

        if overwrite:
            to_update = idx
        else:
            current_missing = base.loc[idx, col].isna() | (base.loc[idx, col].astype(str).str.strip() == "")
            to_update = idx[current_missing]

        base.loc[to_update, col] = values.loc[to_update]

        fill_report.append({
            "conta": col,
            "valores_encontrados_no_relatorio": int(values.notna().sum()),
            "linhas_preenchidas_na_base": int(len(to_update)),
        })

    # Remove controle interno
    base = base.drop(columns=["_row_id"])

    report_summary = pd.DataFrame(fill_report)
    return base, report_summary


def main():
    parser = argparse.ArgumentParser(
        description="Inclui contas selecionadas do IFData na base da dissertação."
    )
    parser.add_argument("--base", required=True, help="Caminho da base .xlsx")
    parser.add_argument(
        "--relatorios",
        nargs="+",
        required=True,
        help="Um ou mais CSVs IFData. Aceita glob, ex.: 'ext_*_t2_r*.csv'"
    )
    parser.add_argument("--saida", default="base_com_contas.xlsx", help="Arquivo .xlsx de saída")
    parser.add_argument("--sheet", default=0, help="Nome ou índice da aba da base. Padrão: primeira aba")
    parser.add_argument(
        "--mapa_codinst",
        default=None,
        help="CSV opcional com colunas id_entidade,CodInst para complementar o mapeamento."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Se informado, sobrescreve valores já existentes nas contas-alvo."
    )

    args = parser.parse_args()

    sheet = int(args.sheet) if str(args.sheet).isdigit() else args.sheet

    report_paths = expand_report_paths(args.relatorios)

    print(f"Lendo base: {args.base}")
    base_df = read_base(args.base, sheet_name=sheet)

    print(f"Lendo {len(report_paths)} relatório(s):")
    for path in report_paths:
        print(f" - {path}")

    report_df = read_reports(report_paths)
    mapping = load_external_mapping(args.mapa_codinst)

    enriched_df, summary = merge_accounts(
        base_df=base_df,
        report_df=report_df,
        mapping=mapping,
        overwrite=args.overwrite,
    )

    enriched_df.to_excel(args.saida, index=False)

    print("\nResumo do preenchimento:")
    if summary.empty:
        print("Nenhuma linha foi preenchida.")
    else:
        print(summary.to_string(index=False))

    print(f"\nArquivo salvo em: {args.saida}")


if __name__ == "__main__":
    main()