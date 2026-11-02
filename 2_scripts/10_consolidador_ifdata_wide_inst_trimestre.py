from __future__ import annotations

import argparse
import csv
import glob
import re
from pathlib import Path
from typing import List, Sequence

import pandas as pd

# python 10_consolidador_ifdata_wide_inst_trimestre.py "ifdata/sanity_check/extracted/*_r4.csv" -o ifdata/sanity_check/consolidado/base_sanity_check.xlsx

PADRAO_NOME_ARQUIVO = re.compile(r"ext_(\d{6})_t(\d+)_r(\d+)\.csv$", re.IGNORECASE)
COLUNAS_ESPERADAS = [
    "TipoInstituicao",
    "CodInst",
    "AnoMes",
    "NomeRelatorio",
    "NumeroRelatorio",
    "Grupo",
    "Conta",
    "NomeColuna",
    "Saldo",
]


def expandir_entradas(entradas: Sequence[str]) -> List[Path]:
    """Expande arquivos, pastas e curingas (*.csv) para uma lista única de Paths."""
    arquivos: List[Path] = []

    for entrada in entradas:
        matches = glob.glob(entrada)
        if matches:
            for match in matches:
                p = Path(match)
                if p.is_file() and p.suffix.lower() == ".csv":
                    arquivos.append(p)
                elif p.is_dir():
                    arquivos.extend(sorted(p.glob("*.csv")))
            continue

        p = Path(entrada)
        if p.is_file() and p.suffix.lower() == ".csv":
            arquivos.append(p)
        elif p.is_dir():
            arquivos.extend(sorted(p.glob("*.csv")))

    vistos = set()
    unicos = []
    for arq in arquivos:
        chave = str(arq.resolve())
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(arq)

    return sorted(unicos, key=lambda p: str(p.resolve()).lower())


def detectar_separador(caminho: Path) -> str:
    """Tenta inferir o separador do CSV a partir da primeira linha."""
    candidatos = [",", ";", "\t", "|"]

    with open(caminho, "r", encoding="utf-8", newline="") as f:
        primeira_linha = f.readline()

    if not primeira_linha:
        return ","

    contagens = {sep: primeira_linha.count(sep) for sep in candidatos}
    sep_escolhido = max(contagens, key=contagens.get)
    return sep_escolhido if contagens[sep_escolhido] > 0 else ","


def ler_csv_robusto(caminho: Path) -> pd.DataFrame:
    """Lê o CSV tentando encodings e separadores comuns."""
    separador = detectar_separador(caminho)
    encodings = ["utf-8", "utf-8-sig", "latin1", "cp1252"]
    erros = []

    for enc in encodings:
        try:
            return pd.read_csv(caminho, sep=separador, encoding=enc)
        except Exception as e:
            erros.append(f"encoding={enc}: {e}")

    for enc in encodings:
        try:
            with open(caminho, "r", encoding=enc, newline="") as f:
                amostra = f.read(4096)
                dialect = csv.Sniffer().sniff(amostra)
                f.seek(0)
                return pd.read_csv(f, sep=dialect.delimiter)
        except Exception as e:
            erros.append(f"sniffer encoding={enc}: {e}")

    raise ValueError(
        f"Não foi possível ler o arquivo {caminho}. Tentativas: {' | '.join(erros)}"
    )


def padronizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Limpa espaços e mantém nomes de colunas consistentes."""
    df = df.copy()
    df.columns = [re.sub(r"\s+", " ", str(col)).strip() for col in df.columns]
    return df


def extrair_metadados_nome_arquivo(nome_arquivo: str) -> dict:
    """Extrai metadados do padrão ext_YYYYMM_tX_rY.csv."""
    m = PADRAO_NOME_ARQUIVO.search(nome_arquivo)
    if not m:
        return {
            "AnoMes_arquivo": None,
            "TipoArquivo": None,
            "RelatorioArquivo": None,
        }

    return {
        "AnoMes_arquivo": int(m.group(1)),
        "TipoArquivo": int(m.group(2)),
        "RelatorioArquivo": int(m.group(3)),
    }


def converter_tipos(df: pd.DataFrame) -> pd.DataFrame:
    """Converte colunas numéricas quando existirem."""
    df = df.copy()

    colunas_int = [
        "TipoInstituicao",
        "AnoMes",
        "NumeroRelatorio",
        "Conta",
        "AnoMes_arquivo",
        "TipoArquivo",
        "RelatorioArquivo",
    ]
    colunas_float = ["Saldo"]

    for col in colunas_int:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    for col in colunas_float:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in ["Grupo", "CodInst", "NomeRelatorio", "NomeColuna", "ArquivoOrigem"]:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype("string")
                .str.replace(r"\s+", " ", regex=True)
                .str.strip()
            )

    return df


def validar_estrutura(df: pd.DataFrame, caminho: Path) -> None:
    """Emite aviso se a estrutura divergir do esperado, mas não interrompe."""
    faltantes = [c for c in COLUNAS_ESPERADAS if c not in df.columns]
    extras = [c for c in df.columns if c not in COLUNAS_ESPERADAS + ["DescricaoColuna"]]

    if faltantes:
        print(f"[aviso] {caminho.name}: colunas faltantes: {faltantes}")
    if "DescricaoColuna" in df.columns:
        print(
            f"[info] {caminho.name}: coluna 'DescricaoColuna' será descartada no resultado final."
        )
    if extras:
        print(f"[info] {caminho.name}: colunas extras detectadas: {extras}")


def consolidar_arquivos_long(
    arquivos: Sequence[str | Path],
    deduplicar: bool = True,
    ordenar: bool = True,
) -> pd.DataFrame:
    """
    Consolida vários CSVs em uma única base long-format.

    Observação
    ----------
    A coluna 'DescricaoColuna' é descartada intencionalmente.
    """
    frames: List[pd.DataFrame] = []

    for arquivo in arquivos:
        caminho = Path(arquivo)
        df = ler_csv_robusto(caminho)
        df = padronizar_colunas(df)
        validar_estrutura(df, caminho)

        if "DescricaoColuna" in df.columns:
            df = df.drop(columns=["DescricaoColuna"])

        meta = extrair_metadados_nome_arquivo(caminho.name)
        for k, v in meta.items():
            df[k] = v
        df["ArquivoOrigem"] = caminho.name

        if "AnoMes" in df.columns and meta.get("AnoMes_arquivo") is not None:
            valores = sorted(
                pd.to_numeric(df["AnoMes"], errors="coerce")
                .dropna()
                .astype(int)
                .unique()
                .tolist()
            )
            if len(valores) > 1:
                print(
                    f"[aviso] {caminho.name}: o conteúdo possui múltiplos valores de AnoMes: {valores[:10]}"
                    + (" ..." if len(valores) > 10 else "")
                )
            elif len(valores) == 1 and valores[0] != int(meta["AnoMes_arquivo"]):
                print(
                    f"[aviso] {caminho.name}: AnoMes do conteúdo ({valores[0]}) "
                    f"difere do nome do arquivo ({meta['AnoMes_arquivo']})."
                )

        frames.append(converter_tipos(df))

    if not frames:
        raise ValueError("Nenhum arquivo CSV válido foi informado.")

    base = pd.concat(frames, ignore_index=True)

    if deduplicar:
        base = base.drop_duplicates().reset_index(drop=True)

    if ordenar:
        chaves_ordenacao = [
            c
            for c in [
                "CodInst",
                "AnoMes",
                "AnoMes_arquivo",
                "NumeroRelatorio",
                "RelatorioArquivo",
                "Conta",
                "NomeColuna",
            ]
            if c in base.columns
        ]
        if chaves_ordenacao:
            base = base.sort_values(chaves_ordenacao).reset_index(drop=True)

    return base


def construir_wide_detalhado(
    base_long: pd.DataFrame,
    aggfunc: str = "first",
    ordenar: bool = True,
) -> pd.DataFrame:
    """
    Monta uma base wide detalhada na granularidade:
    instituição + trimestre + relatório + grupo + metadados de arquivo.

    Essa etapa é intermediária e serve para, em seguida, colapsar
    com segurança para o nível instituição-trimestre.
    """
    colunas_necessarias = ["NomeColuna", "Saldo"]
    faltantes = [c for c in colunas_necessarias if c not in base_long.columns]
    if faltantes:
        raise ValueError(
            f"Não foi possível construir a base wide. Faltam colunas: {faltantes}"
        )

    id_cols = [
        c
        for c in [
            "TipoInstituicao",
            "CodInst",
            "AnoMes",
            "NomeRelatorio",
            "NumeroRelatorio",
            "Grupo",
            "AnoMes_arquivo",
            "TipoArquivo",
            "RelatorioArquivo",
            "ArquivoOrigem",
        ]
        if c in base_long.columns and not base_long[c].isna().all()
    ]

    if not id_cols:
        raise ValueError(
            "Nenhuma coluna identificadora foi encontrada para montar a base wide detalhada."
        )

    duplicados = (
        base_long.groupby(id_cols + ["NomeColuna"], dropna=False)
        .size()
        .reset_index(name="n")
        .query("n > 1")
    )
    if not duplicados.empty:
        print(
            f"[aviso] Foram detectados {len(duplicados)} casos com múltiplos valores para a mesma célula wide detalhada. "
            f"Será aplicado aggfunc='{aggfunc}'."
        )

    base_wide = (
        pd.pivot_table(
            base_long,
            index=id_cols,
            columns="NomeColuna",
            values="Saldo",
            aggfunc=aggfunc,
        )
        .reset_index()
    )

    if isinstance(base_wide.columns, pd.MultiIndex):
        base_wide.columns = [
            " ".join([str(x) for x in col if str(x) != ""]).strip()
            for col in base_wide.columns.to_flat_index()
        ]
    else:
        base_wide.columns = [str(col).strip() for col in base_wide.columns]

    colunas_medidas = [c for c in base_wide.columns if c not in id_cols]
    colunas_finais = id_cols + sorted(colunas_medidas)
    base_wide = base_wide[colunas_finais]

    if ordenar:
        chaves_ordenacao = [
            c for c in ["CodInst", "AnoMes", "NumeroRelatorio", "Grupo"] if c in base_wide.columns
        ]
        if chaves_ordenacao:
            base_wide = base_wide.sort_values(chaves_ordenacao).reset_index(drop=True)

    return base_wide


def validar_conflitos_colapso(
    base_wide_detalhada: pd.DataFrame,
    id_final: Sequence[str],
    colunas_medidas: Sequence[str],
    max_exemplos: int = 10,
) -> None:
    """
    Garante que não existam dois valores diferentes para a mesma variável
    dentro da mesma chave instituição-trimestre.
    """
    if not colunas_medidas:
        return

    nunique = (
        base_wide_detalhada.groupby(list(id_final), dropna=False)[list(colunas_medidas)]
        .nunique(dropna=True)
    )
    mascara = nunique.gt(1)

    if not mascara.any().any():
        return

    conflitos = mascara.stack()
    conflitos = conflitos[conflitos].reset_index()
    conflitos.columns = list(id_final) + ["Variavel", "Conflito"]

    exemplos = []
    for linha in conflitos.head(max_exemplos).itertuples(index=False):
        exemplos.append(
            f"(CodInst={linha.CodInst}, AnoMes={linha.AnoMes}, Variavel={linha.Variavel})"
        )

    raise ValueError(
        "Foram detectados valores conflitantes ao colapsar a base para o nível "
        "instituição-trimestre. Exemplos: " + "; ".join(exemplos)
    )


def colapsar_para_instituicao_trimestre(
    base_wide_detalhada: pd.DataFrame,
    ordenar: bool = True,
) -> pd.DataFrame:
    """
    Colapsa a base wide detalhada para o nível instituição-trimestre.

    Regras:
    - mantém apenas as chaves TipoInstituicao, CodInst e AnoMes;
    - remove metadados de relatório/grupo/arquivo;
    - valida previamente se não há conflitos de valores entre linhas do mesmo período.
    """
    id_final = [
        c for c in ["TipoInstituicao", "CodInst", "AnoMes"] if c in base_wide_detalhada.columns
    ]
    if len(id_final) < 2 or "AnoMes" not in id_final or "CodInst" not in id_final:
        raise ValueError(
            "A base não contém colunas suficientes para colapsar ao nível instituição-trimestre."
        )

    colunas_descartar = [
        c
        for c in [
            "NomeRelatorio",
            "NumeroRelatorio",
            "Grupo",
            "AnoMes_arquivo",
            "TipoArquivo",
            "RelatorioArquivo",
            "ArquivoOrigem",
        ]
        if c in base_wide_detalhada.columns
    ]

    colunas_medidas = [
        c for c in base_wide_detalhada.columns if c not in set(id_final) | set(colunas_descartar)
    ]

    validar_conflitos_colapso(
        base_wide_detalhada=base_wide_detalhada,
        id_final=id_final,
        colunas_medidas=colunas_medidas,
    )

    base_painel = (
        base_wide_detalhada[id_final + colunas_medidas]
        .groupby(id_final, dropna=False, as_index=False)
        .first()
    )

    colunas_finais = id_final + sorted(colunas_medidas)
    base_painel = base_painel[colunas_finais]

    if ordenar:
        chaves_ordenacao = [c for c in ["CodInst", "AnoMes"] if c in base_painel.columns]
        if chaves_ordenacao:
            base_painel = base_painel.sort_values(chaves_ordenacao).reset_index(drop=True)

    return base_painel


def consolidar_arquivos_wide(
    arquivos: Sequence[str | Path],
    aggfunc: str = "first",
    deduplicar: bool = True,
    ordenar: bool = True,
) -> pd.DataFrame:
    """
    Consolida arquivos CSV e retorna uma base wide no nível instituição-trimestre,
    com uma coluna por NomeColuna.

    A tabela final não inclui 'DescricaoColuna', 'Conta', 'Grupo',
    'NomeRelatorio' nem metadados de arquivo.
    """
    base_long = consolidar_arquivos_long(
        arquivos=arquivos,
        deduplicar=deduplicar,
        ordenar=ordenar,
    )

    base_wide_detalhada = construir_wide_detalhado(
        base_long=base_long,
        aggfunc=aggfunc,
        ordenar=ordenar,
    )

    base_wide = colapsar_para_instituicao_trimestre(
        base_wide_detalhada=base_wide_detalhada,
        ordenar=ordenar,
    )

    return base_wide


def salvar_saida(df: pd.DataFrame, caminho_saida: str) -> None:
    """Salva a base consolidada no formato indicado pela extensão."""
    saida = Path(caminho_saida)
    saida.parent.mkdir(parents=True, exist_ok=True)

    if saida.suffix.lower() == ".csv":
        df.to_csv(saida, index=False, encoding="utf-8-sig")
    elif saida.suffix.lower() == ".parquet":
        df.to_parquet(saida, index=False)
    elif saida.suffix.lower() in {".xlsx", ".xls"}:
        df.to_excel(saida, index=False)
    else:
        raise ValueError(
            "Extensão de saída não suportada. Use .csv, .parquet ou .xlsx"
        )


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Consolida arquivos CSV no padrão ext_YYYYMM_tX_rY.csv e retorna uma base wide "
            "no nível instituição-trimestre, com uma coluna por NomeColuna."
        )
    )
    parser.add_argument(
        "entradas",
        nargs="+",
        help="Arquivos, pastas e/ou curingas (*.csv) a consolidar.",
    )
    parser.add_argument(
        "-o",
        "--saida",
        default="base_consolidada_wide.csv",
        help="Caminho do arquivo de saída (.csv, .parquet ou .xlsx).",
    )
    parser.add_argument(
        "--aggfunc",
        choices=["first", "sum", "mean", "max", "min"],
        default="first",
        help=(
            "Função de agregação usada apenas na etapa wide detalhada, "
            "caso existam múltiplos valores para a mesma célula."
        ),
    )
    parser.add_argument(
        "--sem-deduplicar",
        action="store_true",
        help="Não remove linhas duplicadas antes da pivotagem.",
    )
    parser.add_argument(
        "--sem-ordenar",
        action="store_true",
        help="Não ordena a base consolidada.",
    )
    return parser


def main() -> None:
    parser = construir_parser()
    args = parser.parse_args()

    arquivos = expandir_entradas(args.entradas)
    if not arquivos:
        raise SystemExit("Nenhum arquivo CSV encontrado nas entradas informadas.")

    print(f"Arquivos encontrados: {len(arquivos)}")
    for arq in arquivos:
        print(f" - {arq}")

    base = consolidar_arquivos_wide(
        arquivos=arquivos,
        aggfunc=args.aggfunc,
        deduplicar=not args.sem_deduplicar,
        ordenar=not args.sem_ordenar,
    )

    salvar_saida(base, args.saida)

    print("\nConsolidação concluída.")
    print("Formato: wide")
    print("Granularidade final: instituição-trimestre")
    print(
        "Observação: as colunas 'DescricaoColuna', 'Conta', 'Grupo', "
        "'NomeRelatorio' e metadados de arquivo foram removidas da base final."
    )
    print(f"Linhas: {len(base):,}".replace(",", "."))
    print(f"Colunas: {base.shape[1]}")
    print(f"Saída: {args.saida}")


if __name__ == "__main__":
    main()
