#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Consolida a base principal em Excel com a base de liquidez (LCR/NSFR) em CSV.

Lógica principal:
1. Lê a base principal (Excel) e a base de liquidez (CSV).
2. Normaliza identificadores (CNPJ/CNPJ8) e trimestres.
3. Aplica overrides manuais para instituições cujo identificador na base principal
   não coincide com o identificador presente na base de liquidez.
4. Faz o merge por instituição + trimestre.
5. Gera:
   - arquivo consolidado
   - relatório de cobertura do merge
   - arquivo com linhas não casadas

Uso:
    python consolidar_base_bancos_liquidez.py --base bases/base_final_bancos.xlsx --liq bases/lcr_nsfr_resultado.csv --out bases/consolidacao_prudencial/base_final_bancos_consolidada.xlsx
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, Iterable, Optional

import pandas as pd


# Overrides necessários porque a base principal e a base de liquidez não usam,
# em todos os casos, a mesma chave institucional.
# Os códigos abaixo foram inferidos da estrutura da própria base e do mapeamento
# institucional do projeto.
MANUAL_CNPJ8_BY_CODINST: Dict[str, str] = {
    "C0080147": "28127603",  # Banestes
    "C0080154": "93026847",  # Banrisul (na base de liquidez aparece a corretora)
    "C0080123": "34169557",  # Banco Mercantil de Investimentos
    "C0080336": "30306294",  # BTG Pactual
}

BASE_REQUIRED_COLUMNS = ["AnoMes", "CodInst", "cnpj_lider"]
LIQ_REQUIRED_COLUMNS = ["cnpj8", "quarter"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Consolida a base principal com a base de LCR/NSFR."
    )
    parser.add_argument(
        "--base",
        default="base_final_bancos.xlsx",
        help="Caminho do arquivo Excel da base principal.",
    )
    parser.add_argument(
        "--liq",
        default="lcr_nsfr_resultado.csv",
        help="Caminho do arquivo CSV com LCR/NSFR.",
    )
    parser.add_argument(
        "--sheet",
        default=0,
        help="Nome ou índice da aba do Excel a ser lida. Padrão: primeira aba.",
    )
    parser.add_argument(
        "--out",
        default="base_final_bancos_consolidada.xlsx",
        help="Arquivo de saída consolidado (.xlsx ou .csv).",
    )
    parser.add_argument(
        "--report",
        default="relatorio_consolidacao_liquidez.xlsx",
        help="Arquivo de relatório (.xlsx ou .csv).",
    )
    parser.add_argument(
        "--unmatched",
        default="linhas_sem_casamento_liquidez.xlsx",
        help="Arquivo com linhas sem casamento (.xlsx ou .csv).",
    )
    return parser.parse_args()


def sniff_csv_separator(path: Path) -> str:
    with path.open("r", encoding="utf-8-sig", errors="replace") as f:
        first_line = f.readline()
    semicolons = first_line.count(";")
    commas = first_line.count(",")
    return ";" if semicolons >= commas else ","


def normalize_digits(value: object) -> Optional[str]:
    if pd.isna(value):
        return None
    digits = re.sub(r"\D", "", str(value))
    if digits == "":
        return None
    digits = digits.lstrip("0")
    return digits or "0"


def normalize_text(value: object) -> Optional[str]:
    if pd.isna(value):
        return None
    text = str(value).strip().lower()
    text = "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    )
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return text or None


def ensure_columns(df: pd.DataFrame, required: Iterable[str], df_name: str) -> None:
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(
            f"O arquivo '{df_name}' não possui as colunas obrigatórias: {missing}"
        )


def safe_to_int_series(series: pd.Series, column_name: str) -> pd.Series:
    converted = pd.to_numeric(series, errors="coerce")
    if converted.isna().all():
        raise ValueError(
            f"Não foi possível converter a coluna '{column_name}' para trimestre numérico."
        )
    return converted.astype("Int64")


def load_base(path: Path, sheet: object) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=sheet)
    ensure_columns(df, BASE_REQUIRED_COLUMNS, path.name)

    df = df.copy()
    df["AnoMes"] = safe_to_int_series(df["AnoMes"], "AnoMes")
    df["CodInst"] = df["CodInst"].astype(str).str.strip()
    df["cnpj_lider_norm"] = df["cnpj_lider"].apply(normalize_digits)
    df["join_cnpj8"] = df.apply(
        lambda row: MANUAL_CNPJ8_BY_CODINST.get(row["CodInst"], row["cnpj_lider_norm"]),
        axis=1,
    )

    # Auxiliares para diagnóstico
    if "nome" in df.columns:
        df["nome_norm"] = df["nome"].apply(normalize_text)
    else:
        df["nome_norm"] = None

    return df


def load_liquidity(path: Path) -> pd.DataFrame:
    sep = sniff_csv_separator(path)
    df = pd.read_csv(path, sep=sep)
    ensure_columns(df, LIQ_REQUIRED_COLUMNS, path.name)

    df = df.copy()
    df["quarter"] = safe_to_int_series(df["quarter"], "quarter")
    df["join_cnpj8"] = df["cnpj8"].apply(normalize_digits)

    duplicates = df.duplicated(subset=["join_cnpj8", "quarter"], keep=False)
    if duplicates.any():
        dup_sample = df.loc[duplicates, ["cnpj8", "quarter"]].head(10)
        raise ValueError(
            "A base de liquidez possui chaves duplicadas em (cnpj8, quarter). "
            f"Amostra:\n{dup_sample.to_string(index=False)}"
        )

    rename_map = {
        "input_value": "liq_input_value",
        "institution_name": "liq_institution_name",
        "cnpj": "liq_cnpj",
        "cnpj8": "liq_cnpj8",
        "quarter": "liq_quarter",
        "lcr_source": "liq_lcr_source",
        "nsfr_source": "liq_nsfr_source",
        "hqla_source": "liq_hqla_source",
        "net_cash_outflows_source": "liq_net_cash_outflows_source",
        "asf_source": "liq_asf_source",
        "rsf_source": "liq_rsf_source",
        "proxy_source": "liq_proxy_source",
        "proxy_notes": "liq_proxy_notes",
        "observations": "liq_observations",
    }
    df = df.rename(columns=rename_map)
    return df


def build_match_status(merged: pd.DataFrame) -> pd.DataFrame:
    merged = merged.copy()
    merged["merge_status"] = merged["_merge"].map(
        {"both": "casado", "left_only": "sem_casamento"}
    )
    return merged


def build_coverage_report(merged: pd.DataFrame) -> pd.DataFrame:
    institution_col = None
    for candidate in ["ticker_canonico", "nome", "CodInst"]:
        if candidate in merged.columns:
            institution_col = candidate
            break
    if institution_col is None:
        institution_col = "join_cnpj8"

    rep = (
        merged.assign(
            instituicao_reporte=merged[institution_col].fillna(merged.get("CodInst", "SEM_ID"))
        )
        .groupby("instituicao_reporte", dropna=False)
        .agg(
            linhas_base=("AnoMes", "size"),
            linhas_casadas=("merge_status", lambda s: (s == "casado").sum()),
            primeiro_trimestre_base=("AnoMes", "min"),
            ultimo_trimestre_base=("AnoMes", "max"),
            primeiro_trimestre_liq=("liq_quarter", "min"),
            ultimo_trimestre_liq=("liq_quarter", "max"),
        )
        .reset_index()
    )
    rep["cobertura_pct"] = (rep["linhas_casadas"] / rep["linhas_base"] * 100).round(2)
    return rep.sort_values(["cobertura_pct", "instituicao_reporte"], ascending=[False, True])


def save_dataframe(df: pd.DataFrame, path: Path, sheet_name: str = "Sheet1") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()

    if suffix == ".csv":
        df.to_csv(path, index=False, encoding="utf-8-sig")
    elif suffix in {".xlsx", ".xlsm"}:
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    else:
        raise ValueError(
            f"Formato de saída não suportado: '{path.suffix}'. Use .xlsx, .xlsm ou .csv."
        )


def save_report_bundle(
    report_path: Path,
    resumo: pd.DataFrame,
    cobertura: pd.DataFrame,
    unmatched: pd.DataFrame,
) -> None:
    suffix = report_path.suffix.lower()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    if suffix == ".csv":
        # Se o usuário pedir CSV, gravamos apenas o resumo no arquivo principal.
        resumo.to_csv(report_path, index=False, encoding="utf-8-sig")
        cobertura.to_csv(
            report_path.with_name(report_path.stem + "_cobertura.csv"),
            index=False,
            encoding="utf-8-sig",
        )
        unmatched.to_csv(
            report_path.with_name(report_path.stem + "_sem_casamento.csv"),
            index=False,
            encoding="utf-8-sig",
        )
        return

    if suffix not in {".xlsx", ".xlsm"}:
        raise ValueError(
            f"Formato de relatório não suportado: '{report_path.suffix}'. Use .xlsx, .xlsm ou .csv."
        )

    with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
        resumo.to_excel(writer, sheet_name="resumo", index=False)
        cobertura.to_excel(writer, sheet_name="cobertura", index=False)
        unmatched.to_excel(writer, sheet_name="sem_casamento", index=False)


def main() -> int:
    args = parse_args()

    base_path = Path(args.base)
    liq_path = Path(args.liq)
    out_path = Path(args.out)
    report_path = Path(args.report)
    unmatched_path = Path(args.unmatched)

    if not base_path.exists():
        raise FileNotFoundError(f"Arquivo base não encontrado: {base_path}")
    if not liq_path.exists():
        raise FileNotFoundError(f"Arquivo de liquidez não encontrado: {liq_path}")

    base_df = load_base(base_path, args.sheet)
    liq_df = load_liquidity(liq_path)

    liq_cols = [col for col in liq_df.columns if col not in {"join_cnpj8"}]
    merged = base_df.merge(
        liq_df[["join_cnpj8", *liq_cols]],
        left_on=["join_cnpj8", "AnoMes"],
        right_on=["join_cnpj8", "liq_quarter"],
        how="left",
        indicator=True,
    )
    merged = build_match_status(merged)

    coverage_df = build_coverage_report(merged)
    unmatched_df = merged.loc[merged["merge_status"] == "sem_casamento"].copy()

    summary_df = pd.DataFrame(
        {
            "indicador": [
                "linhas_base",
                "linhas_liquidez",
                "linhas_casadas",
                "linhas_sem_casamento",
                "cobertura_pct",
                "trimestre_min_base",
                "trimestre_max_base",
                "trimestre_min_liquidez",
                "trimestre_max_liquidez",
            ],
            "valor": [
                len(base_df),
                len(liq_df),
                int((merged["merge_status"] == "casado").sum()),
                int((merged["merge_status"] == "sem_casamento").sum()),
                round((merged["merge_status"] == "casado").mean() * 100, 2),
                int(base_df["AnoMes"].min()),
                int(base_df["AnoMes"].max()),
                int(liq_df["liq_quarter"].min()),
                int(liq_df["liq_quarter"].max()),
            ],
        }
    )

    # Remover colunas auxiliares pouco úteis no arquivo final.
    cols_to_drop = ["_merge", "nome_norm", "cnpj_lider_norm"]
    merged_final = merged.drop(columns=[c for c in cols_to_drop if c in merged.columns])

    save_dataframe(merged_final, out_path, sheet_name="base_consolidada")
    save_report_bundle(report_path, summary_df, coverage_df, unmatched_df)
    save_dataframe(unmatched_df, unmatched_path, sheet_name="sem_casamento")

    matched = int((merged["merge_status"] == "casado").sum())
    total = len(merged)
    coverage_pct = round(matched / total * 100, 2) if total else 0.0

    print("Consolidação concluída com sucesso.")
    print(f"Base principal         : {base_path}")
    print(f"Base de liquidez       : {liq_path}")
    print(f"Saída consolidada      : {out_path}")
    print(f"Relatório              : {report_path}")
    print(f"Linhas sem casamento   : {unmatched_path}")
    print(f"Linhas casadas         : {matched}/{total} ({coverage_pct}%)")

    if not unmatched_df.empty:
        print("Observação: há linhas sem casamento, o que é esperado quando a base principal")
        print("tem trimestres além do alcance temporal da base de liquidez.")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"[ERRO] {exc}", file=sys.stderr)
        raise
