#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
descritivas_brapi_statements.py

Recebe arquivos JSON no formato do `statements_ABCB4.json` (históricos trimestrais de demonstrativos),
normaliza em tabelas (pandas) e gera análises descritivas.

O que o script entrega (por demonstrativo):
- <outdir>/<statement>/data.csv                      (tabela normalizada)
- <outdir>/<statement>/schema.csv                    (tipos e % numérica)
- <outdir>/<statement>/describe_overall.csv          (estatística descritiva por variável numérica)
- <outdir>/<statement>/describe_by_quarter.csv       (descritivas agregadas por trimestre)
- <outdir>/<statement>/corr_numeric.csv              (correlações entre variáveis numéricas)
- <outdir>/<statement>/outliers_iqr.csv              (contagem de outliers por variável (regra IQR))
E um resumo geral:
- <outdir>/summary_overview.csv                      (linhas/colunas, %missing, #numéricas etc.)

Uso:
  python descritivas_brapi_statements.py data_brapi/raw_json/statements/statements_ABCB4.json --outdir outputs_desc
  python descritivas_brapi_statements.py pasta_com_jsons --outdir outputs_desc --empty-as-missing

Dependências:
  pip install pandas numpy
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd


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

    # remove duplicatas preservando ordem
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
    """
    Converte o JSON em um dict {statement_name: DataFrame}.
    Cada DataFrame contém as linhas trimestrais daquele demonstrativo.
    """
    results = payload.get("results") or []
    acc: Dict[str, List[Dict[str, Any]]] = {v: [] for v in STATEMENT_KEYS.values()}

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
                acc[friendly].append(rec)

    dfs: Dict[str, pd.DataFrame] = {}
    for friendly, rows in acc.items():
        dfs[friendly] = pd.json_normalize(rows, sep=".") if rows else pd.DataFrame()
    return dfs


def ensure_outdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


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


def coerce_numeric(df: pd.DataFrame, exclude: List[str]) -> Tuple[pd.DataFrame, List[str]]:
    """
    Tenta converter colunas para numérico (coerce) e retorna lista de colunas numéricas.
    Exclui colunas meta/time explícitas.
    """
    df = df.copy()
    candidates = [c for c in df.columns if c not in exclude]
    numeric_cols: List[str] = []

    for c in candidates:
        # já numérico?
        if pd.api.types.is_numeric_dtype(df[c]):
            numeric_cols.append(c)
            continue
        # tenta converter (se for string/obj)
        s = df[c]
        if pd.api.types.is_object_dtype(s) or str(s.dtype).startswith("string"):
            converted = pd.to_numeric(s, errors="coerce")
            # heurística: se converter produzir uma fração relevante de valores numéricos, assume numérica
            non_na = converted.notna().sum()
            if non_na > 0:
                frac = non_na / max(1, len(converted))
                if frac >= 0.60:  # 60% ou mais interpretável como número
                    df[c] = converted
                    numeric_cols.append(c)

    return df, sorted(numeric_cols)


def schema_table(df: pd.DataFrame, numeric_cols: List[str]) -> pd.DataFrame:
    rows = []
    n = len(df)
    for c in df.columns:
        s = df[c]
        is_num = c in numeric_cols
        rows.append(
            {
                "column": c,
                "dtype": str(s.dtype),
                "is_numeric": bool(is_num),
                "non_null_count": int(s.notna().sum()),
                "null_count": int(s.isna().sum()),
                "null_pct": float(s.isna().mean()) if n else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values(["is_numeric", "null_pct"], ascending=[False, False]).reset_index(drop=True)


def describe_overall(df: pd.DataFrame, numeric_cols: List[str]) -> pd.DataFrame:
    if not numeric_cols or df.empty:
        return pd.DataFrame()

    desc = df[numeric_cols].describe(percentiles=[0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]).T
    desc = desc.reset_index().rename(columns={"index": "column"})
    # adiciona missing
    desc["missing_count"] = df[numeric_cols].isna().sum().values
    desc["missing_pct"] = (df[numeric_cols].isna().mean().values).astype(float)
    # coef. var (std/mean) com cuidado
    desc["cv"] = np.where(desc["mean"].abs() > 0, desc["std"] / desc["mean"].abs(), np.nan)
    # ordena por dispersão e missing
    return desc.sort_values(["missing_pct", "std"], ascending=[False, False]).reset_index(drop=True)


def describe_by_quarter(df: pd.DataFrame, numeric_cols: List[str]) -> pd.DataFrame:
    if df.empty or "quarter" not in df.columns or not numeric_cols:
        return pd.DataFrame()

    g = df.groupby(["symbol", "quarter"], dropna=False)[numeric_cols]
    out = g.agg(["count", "mean", "std", "min", "median", "max"])
    out.columns = ["__".join(col).strip() for col in out.columns.to_flat_index()]
    out = out.reset_index()
    return out.sort_values(["symbol", "quarter"]).reset_index(drop=True)


def corr_numeric(df: pd.DataFrame, numeric_cols: List[str]) -> pd.DataFrame:
    if not numeric_cols:
        return pd.DataFrame()
    # exige pelo menos 2 variáveis
    if len(numeric_cols) < 2:
        return pd.DataFrame()
    corr = df[numeric_cols].corr(numeric_only=True)
    return corr.reset_index().rename(columns={"index": "column"})


def outliers_iqr(df: pd.DataFrame, numeric_cols: List[str]) -> pd.DataFrame:
    """
    Conta outliers por variável usando regra IQR:
    outlier se x < Q1 - 1.5*IQR ou x > Q3 + 1.5*IQR
    """
    if df.empty or not numeric_cols:
        return pd.DataFrame()

    rows = []
    for c in numeric_cols:
        s = df[c].dropna()
        if s.empty:
            rows.append({"column": c, "outliers_iqr_count": 0, "outliers_iqr_pct": np.nan})
            continue
        q1 = s.quantile(0.25)
        q3 = s.quantile(0.75)
        iqr = q3 - q1
        if pd.isna(iqr) or iqr == 0:
            rows.append({"column": c, "outliers_iqr_count": 0, "outliers_iqr_pct": 0.0})
            continue
        lo = q1 - 1.5 * iqr
        hi = q3 + 1.5 * iqr
        out_ct = int(((s < lo) | (s > hi)).sum())
        rows.append({"column": c, "outliers_iqr_count": out_ct, "outliers_iqr_pct": float(out_ct / len(s))})
    return pd.DataFrame(rows).sort_values(["outliers_iqr_pct", "outliers_iqr_count"], ascending=False).reset_index(drop=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Análises descritivas para JSONs no formato statements_*.json.")
    ap.add_argument("inputs", nargs="+", help="Arquivos .json ou pastas contendo .json")
    ap.add_argument("--outdir", default="outputs_desc", help="Pasta de saída (default: outputs_desc)")
    ap.add_argument("--encoding", default="utf-8", help="Encoding dos JSONs (default: utf-8)")
    ap.add_argument("--empty-as-missing", action="store_true", help="Tratar strings vazias como missing (NaN)")
    ap.add_argument("--min-numeric-frac", type=float, default=0.60,
                    help="Fração mínima (0-1) p/ considerar uma coluna como numérica ao converter (default: 0.60)")
    args = ap.parse_args()

    # usa parâmetro na heurística (global)
    global_min_frac = float(args.min_numeric_frac)

    json_files = iter_json_files(args.inputs)
    if not json_files:
        raise SystemExit("Nenhum arquivo .json encontrado.")

    outdir = Path(args.outdir)
    ensure_outdir(outdir)

    # acumula por statement
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

    overview_rows = []
    for statement_name, parts in acc.items():
        df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
        stmt_dir = outdir / statement_name
        ensure_outdir(stmt_dir)

        if df.empty:
            # outputs vazios
            pd.DataFrame().to_csv(stmt_dir / "data.csv", index=False)
            pd.DataFrame().to_csv(stmt_dir / "schema.csv", index=False)
            pd.DataFrame().to_csv(stmt_dir / "describe_overall.csv", index=False)
            pd.DataFrame().to_csv(stmt_dir / "describe_by_quarter.csv", index=False)
            pd.DataFrame().to_csv(stmt_dir / "corr_numeric.csv", index=False)
            pd.DataFrame().to_csv(stmt_dir / "outliers_iqr.csv", index=False)
            overview_rows.append(
                {"statement": statement_name, "rows": 0, "cols": 0, "numeric_cols": 0, "missing_pct": np.nan}
            )
            continue

        # garante colunas meta primeiro (quando existirem)
        cols = df.columns.tolist()
        meta_first = [c for c in META_COLS if c in cols]
        other = [c for c in cols if c not in meta_first]
        df = df[meta_first + other]

        # conversão numérica com heurística customizada
        # (reaplica com frac custom)
        def coerce_numeric_with_frac(df0: pd.DataFrame, exclude: List[str], min_frac: float) -> Tuple[pd.DataFrame, List[str]]:
            df0 = df0.copy()
            candidates = [c for c in df0.columns if c not in exclude]
            numeric_cols_local: List[str] = []
            for c in candidates:
                if pd.api.types.is_numeric_dtype(df0[c]):
                    numeric_cols_local.append(c)
                    continue
                s = df0[c]
                if pd.api.types.is_object_dtype(s) or str(s.dtype).startswith("string"):
                    converted = pd.to_numeric(s, errors="coerce")
                    non_na = converted.notna().sum()
                    if non_na > 0:
                        frac = non_na / max(1, len(converted))
                        if frac >= min_frac:
                            df0[c] = converted
                            numeric_cols_local.append(c)
            return df0, sorted(numeric_cols_local)

        exclude_cols = ["source_file", "symbol", "statement", "type", "endDate", "quarter", "updatedAt"]
        df, numeric_cols = coerce_numeric_with_frac(df, exclude_cols, global_min_frac)

        # salva base normalizada
        df.to_csv(stmt_dir / "data.csv", index=False)

        # schema
        sch = schema_table(df, numeric_cols)
        sch.to_csv(stmt_dir / "schema.csv", index=False)

        # descritivas overall
        desc = describe_overall(df, numeric_cols)
        desc.to_csv(stmt_dir / "describe_overall.csv", index=False)

        # por trimestre
        byq = describe_by_quarter(df, numeric_cols)
        byq.to_csv(stmt_dir / "describe_by_quarter.csv", index=False)

        # correlação
        corr = corr_numeric(df, numeric_cols)
        corr.to_csv(stmt_dir / "corr_numeric.csv", index=False)

        # outliers (IQR)
        out_iqr = outliers_iqr(df, numeric_cols)
        out_iqr.to_csv(stmt_dir / "outliers_iqr.csv", index=False)

        # overview
        n_rows, n_cols = int(df.shape[0]), int(df.shape[1])
        missing_pct = float(df.isna().sum().sum() / max(1, n_rows * n_cols))
        overview_rows.append(
            {
                "statement": statement_name,
                "rows": n_rows,
                "cols": n_cols,
                "numeric_cols": int(len(numeric_cols)),
                "missing_pct": missing_pct,
                "symbols": int(df["symbol"].nunique()) if "symbol" in df.columns else np.nan,
                "quarters": int(df["quarter"].nunique()) if "quarter" in df.columns else np.nan,
            }
        )

    pd.DataFrame(overview_rows).sort_values(["missing_pct", "rows"], ascending=[False, False]).to_csv(
        outdir / "summary_overview.csv", index=False
    )

    print(f"OK: processados {len(json_files)} arquivo(s). Saídas em: {outdir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
