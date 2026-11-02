#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Converte JSONs de demonstrações financeiras (no padrão do arquivo statements_ABCB4.json)
em uma base wide trimestral, pronta para posterior consolidação com a base wide do IF.Data.

Estrutura esperada (resumida):
- objeto raiz com chave `results`
- cada item em `results` pode conter, entre outras, as listas:
    * balanceSheetHistoryQuarterly
    * incomeStatementHistoryQuarterly
    * valueAddedHistoryQuarterly
    * cashflowHistoryQuarterly

Saída:
- uma linha por Ticker + DataFim
- colunas numéricas/contábeis em formato wide
- colunas prefixadas por bloco para evitar colisões de nomes:
    * bs_  -> balance sheet
    * is_  -> income statement
    * va_  -> value added
    * cf_  -> cash flow

    python json_statements_to_wide.py brapi/*.json -o bases/statements.csv
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from functools import reduce
from typing import Dict, Iterable, List, Optional

import pandas as pd


SECTION_SPECS = {
    "balanceSheetHistoryQuarterly": "bs",
    "incomeStatementHistoryQuarterly": "is",
    "valueAddedHistoryQuarterly": "va",
    "cashflowHistoryQuarterly": "cf",
}

KEY_COLUMNS = ["Ticker", "DataFim", "AnoMes"]
OPTIONAL_META_COLUMNS = ["TipoPeriodo", "Empresa", "EmpresaLonga", "ArquivoOrigem"]


def expand_inputs(paths: List[str]) -> List[str]:
    """Expande arquivos, curinga e pastas em uma lista de JSONs."""
    resolved: List[str] = []

    for item in paths:
        if any(ch in item for ch in "*?[]"):
            resolved.extend(glob.glob(item))
        elif os.path.isdir(item):
            resolved.extend(glob.glob(os.path.join(item, "*.json")))
        else:
            resolved.append(item)

    resolved = [os.path.abspath(p) for p in resolved if p.lower().endswith(".json")]
    resolved = sorted(dict.fromkeys(resolved))
    return resolved



def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)



def normalize_result_container(payload: object) -> List[dict]:
    """Normaliza diferentes possibilidades de estrutura para uma lista de 'results'."""
    if isinstance(payload, dict):
        results = payload.get("results")
        if isinstance(results, list):
            return [r for r in results if isinstance(r, dict)]
        if isinstance(results, dict):
            return [results]
        # fallback: talvez o próprio payload já seja um result object
        return [payload]

    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]

    raise ValueError("Estrutura JSON não reconhecida.")



def coerce_dataframe(section_data: object) -> pd.DataFrame:
    if not isinstance(section_data, list) or len(section_data) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(section_data)
    if df.empty:
        return df
    return df



def prepare_section_dataframe(
    section_df: pd.DataFrame,
    prefix: str,
    fallback_symbol: Optional[str],
    short_name: Optional[str],
    long_name: Optional[str],
    source_file: str,
) -> pd.DataFrame:
    """Padroniza uma seção trimestral e prefixa colunas de conteúdo."""
    if section_df.empty:
        return section_df

    df = section_df.copy()

    if "endDate" not in df.columns:
        raise ValueError("Seção trimestral sem a coluna 'endDate'.")

    df["DataFim"] = pd.to_datetime(df["endDate"], errors="coerce")
    df = df[df["DataFim"].notna()].copy()
    if df.empty:
        return pd.DataFrame()

    if "symbol" in df.columns:
        df["Ticker"] = df["symbol"].fillna(fallback_symbol)
    else:
        df["Ticker"] = fallback_symbol

    if "type" in df.columns:
        df["TipoPeriodo"] = df["type"]
    else:
        df["TipoPeriodo"] = None

    df["Empresa"] = short_name
    df["EmpresaLonga"] = long_name
    df["ArquivoOrigem"] = os.path.basename(source_file)
    df["AnoMes"] = df["DataFim"].dt.strftime("%Y%m")

    reserved = {
        "endDate",
        "symbol",
        "type",
        "Ticker",
        "DataFim",
        "AnoMes",
        "TipoPeriodo",
        "Empresa",
        "EmpresaLonga",
        "ArquivoOrigem",
    }

    rename_map: Dict[str, str] = {}
    for col in df.columns:
        if col not in reserved:
            rename_map[col] = f"{prefix}_{col}"

    df = df.rename(columns=rename_map)

    content_cols = [c for c in df.columns if c.startswith(f"{prefix}_")]
    keep_cols = KEY_COLUMNS + OPTIONAL_META_COLUMNS + content_cols
    keep_cols = [c for c in keep_cols if c in df.columns]

    df = df[keep_cols].copy()

    # Uma linha por ticker/data dentro de cada bloco.
    # Quando houver duplicidade, preserva o primeiro valor não nulo por coluna.
    df = (
        df.sort_values(KEY_COLUMNS)
          .groupby(KEY_COLUMNS, as_index=False)
          .agg(first_valid_series)
    )

    return df



def first_valid_series(series: pd.Series):
    non_null = series.dropna()
    if not non_null.empty:
        return non_null.iloc[0]
    return pd.NA



def merge_section_frames(frames: List[pd.DataFrame]) -> pd.DataFrame:
    non_empty = [f for f in frames if f is not None and not f.empty]
    if not non_empty:
        return pd.DataFrame(columns=KEY_COLUMNS + OPTIONAL_META_COLUMNS)

    def merge_two(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
        overlap_meta = [
            c for c in OPTIONAL_META_COLUMNS + ["TipoPeriodo"]
            if c in left.columns and c in right.columns
        ]

        if overlap_meta:
            right = right.drop(columns=overlap_meta, errors="ignore")

        return pd.merge(left, right, on=KEY_COLUMNS, how="outer")

    merged = reduce(merge_two, non_empty)

    meta_candidates = ["TipoPeriodo", "Empresa", "EmpresaLonga", "ArquivoOrigem"]
    for col in meta_candidates:
        if col not in merged.columns:
            merged[col] = pd.NA

    ordered = KEY_COLUMNS + meta_candidates + [
        c for c in merged.columns if c not in KEY_COLUMNS + meta_candidates
    ]
    return merged[ordered].sort_values(["Ticker", "DataFim"]).reset_index(drop=True)



def parse_single_file(path: str) -> pd.DataFrame:
    payload = load_json(path)
    results = normalize_result_container(payload)

    all_result_frames: List[pd.DataFrame] = []

    for result in results:
        fallback_symbol = result.get("symbol")
        short_name = result.get("shortName")
        long_name = result.get("longName")

        section_frames: List[pd.DataFrame] = []
        for section_name, prefix in SECTION_SPECS.items():
            section_df = coerce_dataframe(result.get(section_name))
            if section_df.empty:
                continue
            prepared = prepare_section_dataframe(
                section_df=section_df,
                prefix=prefix,
                fallback_symbol=fallback_symbol,
                short_name=short_name,
                long_name=long_name,
                source_file=path,
            )
            if not prepared.empty:
                section_frames.append(prepared)

        merged_result = merge_section_frames(section_frames)
        if not merged_result.empty:
            all_result_frames.append(merged_result)

    if not all_result_frames:
        return pd.DataFrame()

    final = pd.concat(all_result_frames, ignore_index=True)
    final = final.sort_values(["Ticker", "DataFim"]).drop_duplicates(subset=["Ticker", "DataFim"], keep="first")
    return final.reset_index(drop=True)



def build_wide_dataset(paths: Iterable[str]) -> pd.DataFrame:
    frames = []
    for path in paths:
        try:
            df = parse_single_file(path)
            if not df.empty:
                frames.append(df)
        except Exception as exc:
            print(f"[aviso] Falha ao processar {path}: {exc}")

    if not frames:
        return pd.DataFrame()

    final = pd.concat(frames, ignore_index=True)
    final = final.sort_values(["Ticker", "DataFim", "ArquivoOrigem"], na_position="last")
    final = final.drop_duplicates(subset=["Ticker", "DataFim"], keep="first").reset_index(drop=True)

    # Colunas ordenadas: chaves, metadados e demais variáveis wide.
    priority = KEY_COLUMNS + ["TipoPeriodo", "Empresa", "EmpresaLonga", "ArquivoOrigem"]
    ordered_cols = priority + [c for c in final.columns if c not in priority]
    final = final[ordered_cols]

    return final



def save_output(df: pd.DataFrame, output_path: str) -> None:
    ext = os.path.splitext(output_path)[1].lower()

    if ext == ".csv":
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
    elif ext == ".xlsx":
        df.to_excel(output_path, index=False)
    elif ext == ".parquet":
        df.to_parquet(output_path, index=False)
    else:
        raise ValueError("Formato de saída não suportado. Use .csv, .xlsx ou .parquet")



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Converte JSONs de demonstrações financeiras em base wide trimestral."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Arquivos .json, pasta com JSONs ou curinga (*.json).",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Arquivo de saída (.csv, .xlsx ou .parquet).",
    )
    return parser



def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    input_files = expand_inputs(args.inputs)
    if not input_files:
        raise SystemExit("Nenhum arquivo JSON encontrado.")

    df = build_wide_dataset(input_files)
    if df.empty:
        raise SystemExit("Nenhum dado trimestral foi extraído dos JSONs informados.")

    save_output(df, args.output)

    print("Arquivos lidos:", len(input_files))
    print("Linhas finais:", len(df))
    print("Colunas finais:", len(df.columns))
    print("Saída:", os.path.abspath(args.output))


if __name__ == "__main__":
    main()
