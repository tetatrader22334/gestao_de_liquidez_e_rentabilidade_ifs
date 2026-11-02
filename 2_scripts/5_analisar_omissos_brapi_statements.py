#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analisar_omissos_brapi_statements.py

Lê arquivos JSON no formato de "statements" (ex.: BRAPI /quote com históricos trimestrais),
normaliza em tabelas (pandas) e faz análise de dados omissos (missing values).

Saídas (por tipo de demonstrativo):
- <outdir>/<statement>/data.csv
- <outdir>/<statement>/missing_by_column.csv
- <outdir>/<statement>/missing_by_period.csv
- <outdir>/<statement>/missing_rows.csv

Uso:
  python analisar_omissos_brapi_statements.py data_brapi/raw_json/statements/statements_BBAS3.json --outdir outputs_missing
  python analisar_omissos_brapi_statements.py /pasta_com_jsons --empty-as-missing

Obs.: "dados omissos" = valores nulos/ausentes (NaN/None) e, opcionalmente, strings vazias.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import numpy as np


STATEMENT_KEYS = {
    "balanceSheetHistoryQuarterly": "balance_sheet_quarterly",
    "incomeStatementHistoryQuarterly": "income_statement_quarterly",
    "cashflowHistoryQuarterly": "cashflow_quarterly",
    "valueAddedHistoryQuarterly": "value_added_quarterly",
}

META_COLS = ["source_file", "symbol", "statement", "type", "endDate", "quarter", "updatedAt"]


def iter_json_files(inputs: List[str]) -> List[Path]:
    files: List[Path] = []
    for raw in inputs:
        p = Path(raw).expanduser()
        if p.is_dir():
            files.extend(sorted(p.glob("*.json")))
        elif p.is_file():
            files.append(p)
        else:
            raise FileNotFoundError(f"Entrada não encontrada: {raw}")

    seen = set()
    out = []
    for f in files:
        rp = f.resolve()
        if rp not in seen:
            out.append(f)
            seen.add(rp)
    return out


def load_json(path: Path, encoding: str = "utf-8") -> Dict[str, Any]:
    with path.open("r", encoding=encoding) as f:
        return json.load(f)


def normalize_statements(payload: Dict[str, Any], source_file: str) -> Dict[str, pd.DataFrame]:
    results = payload.get("results") or []
    out: Dict[str, List[Dict[str, Any]]] = {v: [] for v in STATEMENT_KEYS.values()}

    for res in results:
        symbol = res.get("symbol")
        for raw_key, friendly in STATEMENT_KEYS.items():
            rows = res.get(raw_key) or []
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                rec = dict(row)
                rec["symbol"] = symbol
                rec["statement"] = friendly
                rec["source_file"] = source_file
                out[friendly].append(rec)

    dfs: Dict[str, pd.DataFrame] = {}
    for friendly, rows in out.items():
        dfs[friendly] = pd.json_normalize(rows, sep=".") if rows else pd.DataFrame()
    return dfs


def add_time_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "endDate" in df.columns:
        dt = pd.to_datetime(df["endDate"], errors="coerce")
        df["endDate"] = dt.dt.date.astype("object")
        df["quarter"] = dt.dt.to_period("Q").astype("string")
    else:
        df["endDate"] = pd.Series([None] * len(df), dtype="object")
        df["quarter"] = pd.Series([None] * len(df), dtype="string")
    return df


def apply_empty_as_missing(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    obj_cols = [c for c in df.columns if df[c].dtype == "object" or str(df[c].dtype).startswith("string")]
    if obj_cols:
        df[obj_cols] = df[obj_cols].replace(r"^\s*$", np.nan, regex=True)
    return df


def missing_by_column(df: pd.DataFrame) -> pd.DataFrame:
    n = len(df)
    rows = []
    for col in df.columns:
        miss = int(df[col].isna().sum())
        rows.append(
            {
                "column": col,
                "missing_count": miss,
                "non_missing_count": int(n - miss),
                "missing_pct": float(miss / n) if n else np.nan,
                "dtype": str(df[col].dtype),
            }
        )
    out = pd.DataFrame(rows).sort_values(["missing_pct", "missing_count"], ascending=False)
    return out.reset_index(drop=True)


def missing_by_period(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["endDate", "quarter", "rows", "missing_cells", "total_cells", "missing_pct"])

    cols = [c for c in df.columns if c not in ("source_file", "symbol", "statement")]
    data_cols = [c for c in cols if c not in ("type", "endDate", "quarter", "updatedAt")]

    g = df.groupby(["endDate", "quarter"], dropna=False)
    out_rows = []
    for (endDate, quarter), sub in g:
        missing_cells = int(sub[data_cols].isna().sum().sum()) if data_cols else 0
        total_cells = int(sub.shape[0] * len(data_cols)) if data_cols else 0
        out_rows.append(
            {
                "endDate": endDate,
                "quarter": quarter,
                "rows": int(sub.shape[0]),
                "missing_cells": missing_cells,
                "total_cells": total_cells,
                "missing_pct": float(missing_cells / total_cells) if total_cells else np.nan,
            }
        )
    out = pd.DataFrame(out_rows).sort_values(["endDate"], ascending=False)
    return out.reset_index(drop=True)


def missing_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    cols = [c for c in df.columns if c not in ("source_file", "symbol", "statement")]
    data_cols = [c for c in cols if c not in ("type", "endDate", "quarter", "updatedAt")]

    sub = df.copy()
    sub["missing_cells"] = sub[data_cols].isna().sum(axis=1) if data_cols else 0
    sub["total_cells"] = len(data_cols)
    sub["missing_pct"] = sub["missing_cells"] / sub["total_cells"] if data_cols else np.nan

    sub = sub.sort_values(["missing_pct", "missing_cells", "endDate"], ascending=[False, False, False])

    keep_cols = [c for c in META_COLS if c in sub.columns] + ["missing_cells", "total_cells", "missing_pct"]
    return sub[keep_cols].reset_index(drop=True)


def ensure_outdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Análise de dados omissos em JSONs de demonstrativos (statements).")
    ap.add_argument("inputs", nargs="+", help="Arquivos .json ou pastas contendo .json")
    ap.add_argument("--outdir", default="outputs_missing", help="Pasta de saída (default: outputs_missing)")
    ap.add_argument("--encoding", default="utf-8", help="Encoding dos JSONs (default: utf-8)")
    ap.add_argument("--empty-as-missing", action="store_true", help="Tratar strings vazias como missing (NaN)")
    ap.add_argument("--row-missing-threshold", type=float, default=0.5, help="Limite (0-1) p/ destacar linhas (default: 0.5)")
    ap.add_argument("--col-missing-threshold", type=float, default=0.5, help="Limite (0-1) p/ destacar colunas (default: 0.5)")
    args = ap.parse_args()

    json_files = iter_json_files(args.inputs)
    if not json_files:
        raise SystemExit("Nenhum arquivo .json encontrado.")

    outdir = Path(args.outdir)
    ensure_outdir(outdir)

    acc: Dict[str, List[pd.DataFrame]] = {v: [] for v in STATEMENT_KEYS.values()}

    for f in json_files:
        payload = load_json(f, encoding=args.encoding)
        dfs = normalize_statements(payload, source_file=f.name)

        for statement_name, df in dfs.items():
            if df.empty:
                continue
            df = add_time_cols(df)
            if args.empty_as_missing:
                df = apply_empty_as_missing(df)
            acc[statement_name].append(df)

    summary_rows = []
    for statement_name, parts in acc.items():
        df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
        stmt_dir = outdir / statement_name
        ensure_outdir(stmt_dir)

        if df.empty:
            pd.DataFrame().to_csv(stmt_dir / "data.csv", index=False)
            pd.DataFrame().to_csv(stmt_dir / "missing_by_column.csv", index=False)
            pd.DataFrame().to_csv(stmt_dir / "missing_by_period.csv", index=False)
            pd.DataFrame().to_csv(stmt_dir / "missing_rows.csv", index=False)
            continue

        cols = df.columns.tolist()
        meta_first = [c for c in META_COLS if c in cols]
        other = [c for c in cols if c not in meta_first]
        df = df[meta_first + other]

        df.to_csv(stmt_dir / "data.csv", index=False)

        mbc = missing_by_column(df)
        mbc.to_csv(stmt_dir / "missing_by_column.csv", index=False)

        mbp = missing_by_period(df)
        mbp.to_csv(stmt_dir / "missing_by_period.csv", index=False)

        mbr = missing_rows(df)
        mbr.to_csv(stmt_dir / "missing_rows.csv", index=False)

        n_rows, n_cols = int(df.shape[0]), int(df.shape[1])
        total_cells = n_rows * n_cols
        missing_cells = int(df.isna().sum().sum())
        summary_rows.append(
            {
                "statement": statement_name,
                "rows": n_rows,
                "cols": n_cols,
                "missing_cells": missing_cells,
                "total_cells": total_cells,
                "missing_pct": float(missing_cells / total_cells) if total_cells else np.nan,
                "cols_above_threshold": int((mbc["missing_pct"] >= args.col_missing_threshold).sum()),
                "rows_above_threshold": int((mbr["missing_pct"] >= args.row_missing_threshold).sum()) if not mbr.empty else 0,
            }
        )

        mbc.loc[mbc["missing_pct"] >= args.col_missing_threshold].to_csv(stmt_dir / "columns_flagged.csv", index=False)
        (mbr.loc[mbr["missing_pct"] >= args.row_missing_threshold] if not mbr.empty else pd.DataFrame()).to_csv(
            stmt_dir / "rows_flagged.csv", index=False
        )

    pd.DataFrame(summary_rows).sort_values("missing_pct", ascending=False).to_csv(outdir / "summary_missingness.csv", index=False)

    print(f"OK: processados {len(json_files)} arquivo(s). Saídas em: {outdir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
