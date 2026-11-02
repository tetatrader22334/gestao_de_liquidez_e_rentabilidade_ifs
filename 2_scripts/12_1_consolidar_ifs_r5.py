import argparse
from pathlib import Path
import pandas as pd


def build_codinst_to_baseifs_id():
    """
    Mapeia os códigos da base_r5 para o identificador usado na base_ifs.
    Observações:
    - Alguns ids da base_ifs aparecem como ticker (ex.: ABCB4, BBDC4).
    - Outros aparecem como código prudencial (ex.: C0080123, C0080336).
    - Alguns tickers na base_ifs usam classes diferentes das informadas no mercado
      (ex.: RPAD6, BRSR6, PINE4). O mapeamento abaixo já trata esses aliases.
    """
    # python 12_1_consolidar_ifs_r5.py --base-ifs bases/base_ifs.xlsx --base-r5 bases/base_r5.xlsx --output bases/base_consolidada_ifs_r5.xlsx
    
    return {
        # Alfa Holding
        "C0010083": "RPAD6",
        "C0080109": "RPAD6",

        # Banestes
        "C0030159": "BEES4",
        "C0080147": "BEES4",

        # ABC Brasil
        "C0041856": "ABCB4",
        "C0080312": "ABCB4",

        # Banco da Amazônia
        "C0081249": "BAZA3",

        # Bradesco
        "C0010045": "BBDC4",
        "C0080075": "BBDC4",

        # Banco do Brasil
        "C0049906": "BBAS3",
        "C0080329": "BBAS3",

        # BTG Pactual / Banco Pan
        # Na base_ifs, o identificador aparece como o código prudencial C0080336.
        "C0049944": "C0080336",
        "C0080336": "C0080336",

        # Banco do Estado de Sergipe
        "C0081634": "BGIP4",

        # Banrisul
        "C0030173": "BRSR6",
        "C0080154": "BRSR6",

        # Mercantil (na base_ifs aparece como código prudencial)
        "C0020152": "C0080123",
        "C0080123": "C0080123",

        # Banco do Nordeste
        "C0081593": "BNBR3",

        # Banco Pine
        "C0050304": "PINE4",
        "C0080374": "PINE4",

        # Santander
        "C0030379": "SANB11",
        "C0080185": "SANB11",

        # BRB
        "C0031976": "BSLI4",
        "C0080288": "BSLI4",
    }


def normalize_keys(df_ifs: pd.DataFrame, df_r5: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df_ifs = df_ifs.copy()
    df_r5 = df_r5.copy()

    df_ifs["AnoMes"] = pd.to_numeric(df_ifs["AnoMes"], errors="coerce").astype("Int64")
    df_ifs["id_entidade"] = df_ifs["id_entidade"].astype(str).str.strip()

    df_r5["AnoMes"] = pd.to_numeric(df_r5["AnoMes"], errors="coerce").astype("Int64")
    df_r5["CodInst"] = df_r5["CodInst"].astype(str).str.strip()
    df_r5.loc[df_r5["CodInst"].isin(["nan", "None", ""]), "CodInst"] = pd.NA

    codinst_to_baseifs_id = build_codinst_to_baseifs_id()
    df_r5["id_entidade"] = df_r5["CodInst"].map(codinst_to_baseifs_id)

    return df_ifs, df_r5


def remove_fully_empty_rows(df: pd.DataFrame) -> pd.DataFrame:
    return df.dropna(how="all").copy()


def consolidate_bases(
    base_ifs_path: str,
    base_r5_path: str,
    output_path: str,
    ifs_sheet: str | None = None,
    r5_sheet: str | None = None,
) -> None:
    df_ifs = pd.read_excel(base_ifs_path, sheet_name=ifs_sheet or 0)
    df_r5 = pd.read_excel(base_r5_path, sheet_name=r5_sheet or 0)

    df_ifs = remove_fully_empty_rows(df_ifs)
    df_r5 = remove_fully_empty_rows(df_r5)

    df_ifs, df_r5 = normalize_keys(df_ifs, df_r5)

    # Remove linhas problemáticas sem chave de instituição na base_r5
    df_r5 = df_r5.dropna(subset=["CodInst"]).copy()

    # Checagem de mapeamento
    unmapped_codes = sorted(df_r5.loc[df_r5["id_entidade"].isna(), "CodInst"].dropna().unique().tolist())
    if unmapped_codes:
        raise ValueError(
            "Existem CodInst sem correspondência no mapeamento: "
            + ", ".join(unmapped_codes)
        )

    # Mantém só uma linha por chave na base_r5, caso haja duplicidade
    dup_mask = df_r5.duplicated(subset=["AnoMes", "id_entidade"], keep=False)
    if dup_mask.any():
        duplicated = (
            df_r5.loc[dup_mask, ["AnoMes", "CodInst", "id_entidade"]]
            .sort_values(["id_entidade", "AnoMes", "CodInst"])
        )
        raise ValueError(
            "Há duplicidades na base_r5 após normalização por ['AnoMes', 'id_entidade'].\n"
            f"{duplicated.to_string(index=False)}"
        )

    # Remove colunas repetidas da base_r5, preservando as da base_ifs
    protected_cols = {"AnoMes", "id_entidade"}
    duplicate_cols = [c for c in df_r5.columns if c in df_ifs.columns and c not in protected_cols]
    df_r5_reduced = df_r5.drop(columns=duplicate_cols)

    # Consolidação
    df_final = df_ifs.merge(
        df_r5_reduced,
        on=["AnoMes", "id_entidade"],
        how="left",
        validate="one_to_one",
    )

    # Diagnóstico útil
    matched = df_final["CodInst"].notna().sum() if "CodInst" in df_final.columns else 0
    unmatched = len(df_final) - matched

    # Salva a base consolidada e uma aba de diagnóstico
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_final.to_excel(writer, sheet_name="base_consolidada", index=False)

        pd.DataFrame({"colunas_duplicadas_removidas_r5": duplicate_cols}).to_excel(
            writer, sheet_name="diagnostico_colunas", index=False
        )

        df_unmatched = df_final.loc[df_final["CodInst"].isna(), ["AnoMes", "id_entidade"]].copy() \
            if "CodInst" in df_final.columns else pd.DataFrame(columns=["AnoMes", "id_entidade"])

        resumo = pd.DataFrame(
            {
                "indicador": [
                    "linhas_base_ifs",
                    "linhas_base_r5_validas",
                    "linhas_base_final",
                    "matches_r5",
                    "linhas_sem_match_r5",
                    "qtd_colunas_duplicadas_removidas_r5",
                ],
                "valor": [
                    len(df_ifs),
                    len(df_r5),
                    len(df_final),
                    matched,
                    unmatched,
                    len(duplicate_cols),
                ],
            }
        )
        resumo.to_excel(writer, sheet_name="diagnostico_resumo", index=False)
        df_unmatched.to_excel(writer, sheet_name="diagnostico_sem_match", index=False)

    print(f"Arquivo consolidado salvo em: {output_path}")
    print(f"Colunas duplicadas removidas da base_r5: {len(duplicate_cols)}")
    print(f"Linhas com match na r5: {matched}")
    print(f"Linhas sem match na r5: {unmatched}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Consolida base_ifs e base_r5, removendo colunas duplicadas."
    )
    parser.add_argument("--base-ifs", default="base_ifs.xlsx", help="Caminho da base_ifs.xlsx")
    parser.add_argument("--base-r5", default="base_r5.xlsx", help="Caminho da base_r5.xlsx")
    parser.add_argument(
        "--output",
        default="base_consolidada_ifs_r5.xlsx",
        help="Caminho do arquivo consolidado de saída",
    )
    parser.add_argument("--ifs-sheet", default=None, help="Nome da aba da base_ifs")
    parser.add_argument("--r5-sheet", default=None, help="Nome da aba da base_r5")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    consolidate_bases(
        base_ifs_path=args.base_ifs,
        base_r5_path=args.base_r5,
        output_path=args.output,
        ifs_sheet=args.ifs_sheet,
        r5_sheet=args.r5_sheet,
    )
