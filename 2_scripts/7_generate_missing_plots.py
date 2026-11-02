#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_missing_plots.py

Gera os plots das análises 1, 2, 3 e 4 a partir dos CSVs:
- missing_by_period.csv
- missing_by_column.csv
- missing_rows.csv
- rows_flagged.csv
- columns_flagged.csv (opcional)

Saída: PNGs em um diretório de output.

Exemplos:
  python generate_missing_plots.py --input-dir outputs_missing_brapi/outputs_missing_ABCB4/balance_sheet_quarterly --out-dir plots_missing_balance_sheet
  python generate_missing_plots.py --missing-by-period missing_by_period.csv --out-dir plots
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional, Tuple, List, Dict

import pandas as pd
import matplotlib.pyplot as plt


# -----------------------------
# Helpers
# -----------------------------
def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    df = pd.read_csv(path)
    return df


def _ensure_missing_pct(df: pd.DataFrame) -> pd.DataFrame:
    """
    Garante uma coluna missing_pct (0-1 ou 0-100 dependendo do input).
    Se vier em porcentagem 0-100, mantém como 0-100 mas marca para plotar adequadamente.
    """
    if "missing_pct" in df.columns:
        return df

    # Possíveis alternativas
    if {"missing_cells", "total_cells"}.issubset(df.columns):
        df["missing_pct"] = (df["missing_cells"] / df["total_cells"]) * 100.0
        return df

    if {"missing_count", "total_count"}.issubset(df.columns):
        df["missing_pct"] = (df["missing_count"] / df["total_count"]) * 100.0
        return df

    raise ValueError(
        "Não encontrei 'missing_pct' nem consegui inferir a partir de "
        "('missing_cells','total_cells') ou ('missing_count','total_count')."
    )


def _is_pct_0_100(series: pd.Series) -> bool:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return True
    # Heurística: se valores > 1.5, provavelmente está em 0-100
    return float(s.quantile(0.95)) > 1.5


def _infer_time_column(df: pd.DataFrame) -> str:
    """
    Tenta inferir a coluna temporal (prioridade):
    endDate > quarter > period > date > dt
    """
    for c in ["endDate", "quarter", "period", "date", "dt"]:
        if c in df.columns:
            return c
    # fallback: primeira coluna que pareça tempo
    for c in df.columns:
        if "date" in c.lower() or "quarter" in c.lower() or "period" in c.lower():
            return c
    raise ValueError("Não consegui inferir a coluna temporal (ex.: 'quarter' ou 'endDate').")


def _parse_time_for_sorting(df: pd.DataFrame, time_col: str) -> Tuple[pd.DataFrame, str]:
    """
    Cria uma coluna auxiliar _t para ordenação.
    Suporta:
      - strings tipo '2010Q1'
      - datas tipo '2010-03-31'
      - timestamps
    Retorna df e nome da coluna label (para eixos).
    """
    s = df[time_col].astype(str)

    # tenta PeriodIndex trimestral (2010Q1)
    try:
        p = pd.PeriodIndex(s, freq="Q")
        df = df.copy()
        df["_t"] = p.to_timestamp(how="end")  # fim do trimestre
        return df, time_col
    except Exception:
        pass

    # tenta datetime
    dt = pd.to_datetime(df[time_col], errors="coerce")
    if dt.notna().any():
        df = df.copy()
        df["_t"] = dt
        return df, time_col

    # fallback: ordenação lexical
    df = df.copy()
    df["_t"] = s
    return df, time_col


def _infer_year_from_time(df: pd.DataFrame) -> pd.Series:
    """
    Infere o ano a partir de _t (datetime) ou da string original.
    """
    if "_t" in df.columns and pd.api.types.is_datetime64_any_dtype(df["_t"]):
        return df["_t"].dt.year

    # fallback: tenta extrair 4 dígitos do início
    s = df.iloc[:, 0].astype(str)
    year = s.str.extract(r"(\d{4})", expand=False)
    return pd.to_numeric(year, errors="coerce")


def _common_key(df_a: pd.DataFrame, df_b: pd.DataFrame) -> Optional[str]:
    """
    Encontra uma chave comum plausível para merge entre missing_rows e rows_flagged.
    """
    candidates = ["row_id", "idx", "index", "endDate", "quarter", "period"]
    for c in candidates:
        if c in df_a.columns and c in df_b.columns:
            return c
    return None


def _savefig(out_path: Path, dpi: int = 180) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close()


# -----------------------------
# Plots: Análises 1 e 2 (by period)
# -----------------------------
def plots_by_period(df_period: pd.DataFrame, out_dir: Path) -> None:
    df_period = _ensure_missing_pct(df_period)
    time_col = _infer_time_column(df_period)
    df_period, _ = _parse_time_for_sorting(df_period, time_col)
    df_period = df_period.sort_values("_t")

    pct_is_0_100 = _is_pct_0_100(df_period["missing_pct"])

    # (1a) Série temporal missing_pct
    plt.figure(figsize=(11, 4))
    plt.plot(df_period["_t"], pd.to_numeric(df_period["missing_pct"], errors="coerce"), marker="o")
    plt.title("Missing ao longo do tempo (missing_pct)")
    plt.xlabel(time_col)
    plt.ylabel("Missing (%)" if pct_is_0_100 else "Missing (fração)")
    plt.xticks(rotation=45, ha="right")
    _savefig(out_dir / "01a_missing_pct_timeseries.png")

    # (1b) Barras empilhadas: missing_cells vs non_missing_cells
    if {"missing_cells", "total_cells"}.issubset(df_period.columns):
        missing = pd.to_numeric(df_period["missing_cells"], errors="coerce").fillna(0)
        total = pd.to_numeric(df_period["total_cells"], errors="coerce").fillna(0)
        non_missing = (total - missing).clip(lower=0)

        plt.figure(figsize=(11, 4.5))
        plt.bar(df_period["_t"], non_missing, label="Não-missing")
        plt.bar(df_period["_t"], missing, bottom=non_missing, label="Missing")
        plt.title("Volume de células missing vs não-missing por período")
        plt.xlabel(time_col)
        plt.ylabel("Células")
        plt.xticks(rotation=45, ha="right")
        plt.legend()
        _savefig(out_dir / "01b_missing_cells_stacked.png")

    # (2a) Histograma missing_pct
    plt.figure(figsize=(7.5, 4.5))
    vals = pd.to_numeric(df_period["missing_pct"], errors="coerce").dropna()
    plt.hist(vals, bins=20)
    plt.title("Distribuição de missing_pct (histograma)")
    plt.xlabel("Missing (%)" if pct_is_0_100 else "Missing (fração)")
    plt.ylabel("Frequência (períodos)")
    _savefig(out_dir / "02a_missing_pct_hist.png")

    # (2b) Boxplot por ano
    years = _infer_year_from_time(df_period)
    df_box = df_period.copy()
    df_box["year"] = years
    df_box = df_box.dropna(subset=["year"])
    df_box["year"] = df_box["year"].astype(int)

    grouped: Dict[int, List[float]] = (
        df_box.groupby("year")["missing_pct"]
        .apply(lambda s: pd.to_numeric(s, errors="coerce").dropna().tolist())
        .to_dict()
    )
    grouped = {k: v for k, v in grouped.items() if len(v) > 0}

    if grouped:
        years_sorted = sorted(grouped.keys())
        data = [grouped[y] for y in years_sorted]

        plt.figure(figsize=(11, 4.5))
        plt.boxplot(data, labels=[str(y) for y in years_sorted], showfliers=True)
        plt.title("Missing_pct por ano (boxplot)")
        plt.xlabel("Ano")
        plt.ylabel("Missing (%)" if pct_is_0_100 else "Missing (fração)")
        plt.xticks(rotation=45, ha="right")
        _savefig(out_dir / "02b_missing_pct_boxplot_by_year.png")


# -----------------------------
# Plots: Análise 3 (by column)
# -----------------------------
def plots_by_column(df_col: pd.DataFrame, out_dir: Path, top_n: int = 20) -> None:
    df_col = _ensure_missing_pct(df_col)

    # Infer col name da variável
    colname = "column" if "column" in df_col.columns else None
    if colname is None:
        # tenta alternativa comum
        for c in ["col", "field", "variable", "name"]:
            if c in df_col.columns:
                colname = c
                break
    if colname is None:
        raise ValueError("Não encontrei a coluna identificadora da variável (ex.: 'column').")

    pct_is_0_100 = _is_pct_0_100(df_col["missing_pct"])

    # (3a) Barplot ordenado (Top N) por missing_pct
    df_plot = df_col.copy()
    df_plot["missing_pct_num"] = pd.to_numeric(df_plot["missing_pct"], errors="coerce")
    df_plot = df_plot.dropna(subset=["missing_pct_num"])
    df_plot = df_plot.sort_values("missing_pct_num", ascending=False).head(top_n)

    plt.figure(figsize=(10.5, 6))
    plt.barh(df_plot[colname].astype(str), df_plot["missing_pct_num"])
    plt.gca().invert_yaxis()
    plt.title(f"Top {top_n} colunas com maior missing_pct")
    plt.xlabel("Missing (%)" if pct_is_0_100 else "Missing (fração)")
    plt.ylabel("Coluna")
    _savefig(out_dir / "03a_top_missing_pct_by_column.png")

    # (3b) Pareto (missing_count) se existir
    if "missing_count" in df_col.columns:
        df_p = df_col.copy()
        df_p["missing_count_num"] = pd.to_numeric(df_p["missing_count"], errors="coerce").fillna(0)
        df_p = df_p.sort_values("missing_count_num", ascending=False)

        total = float(df_p["missing_count_num"].sum()) if df_p["missing_count_num"].sum() else 1.0
        df_p["cum_pct"] = df_p["missing_count_num"].cumsum() / total * 100.0

        # Limita para não ficar ilegível
        df_p2 = df_p.head(max(top_n, 30))

        fig, ax1 = plt.subplots(figsize=(11, 5))
        ax1.bar(df_p2[colname].astype(str), df_p2["missing_count_num"])
        ax1.set_title("Pareto de missing_count (Top colunas)")
        ax1.set_ylabel("Missing (contagem)")
        ax1.set_xlabel("Coluna")
        ax1.tick_params(axis="x", rotation=65)

        ax2 = ax1.twinx()
        ax2.plot(df_p2[colname].astype(str), df_p2["cum_pct"], marker="o")
        ax2.set_ylabel("Acumulado (%)")

        _savefig(out_dir / "03b_pareto_missing_count.png")

    # (3c) Barras por dtype (média de missing_pct)
    if "dtype" in df_col.columns:
        df_d = df_col.copy()
        df_d["missing_pct_num"] = pd.to_numeric(df_d["missing_pct"], errors="coerce")
        df_d = df_d.dropna(subset=["missing_pct_num", "dtype"])
        grp = df_d.groupby("dtype")["missing_pct_num"].mean().sort_values(ascending=False)

        if not grp.empty:
            plt.figure(figsize=(9, 4.5))
            plt.bar(grp.index.astype(str), grp.values)
            plt.title("Missing médio por dtype")
            plt.xlabel("dtype")
            plt.ylabel("Missing (%)" if pct_is_0_100 else "Missing (fração)")
            plt.xticks(rotation=45, ha="right")
            _savefig(out_dir / "03c_missing_pct_by_dtype.png")


# -----------------------------
# Plots: Análise 4 (rows / observações)
# -----------------------------
def plots_by_rows(df_rows: pd.DataFrame, df_rows_flagged: Optional[pd.DataFrame], out_dir: Path, top_n: int = 20) -> None:
    df_rows = _ensure_missing_pct(df_rows)
    time_col = _infer_time_column(df_rows)
    df_rows, _ = _parse_time_for_sorting(df_rows, time_col)

    pct_is_0_100 = _is_pct_0_100(df_rows["missing_pct"])

    # Preparar flagged
    flagged_mask = pd.Series(False, index=df_rows.index)
    merge_key = None

    if df_rows_flagged is not None and not df_rows_flagged.empty:
        merge_key = _common_key(df_rows, df_rows_flagged)
        if merge_key is not None:
            df_rows_flagged_key = df_rows_flagged[[merge_key]].dropna().astype(str)
            flagged_values = set(df_rows_flagged_key[merge_key].tolist())
            flagged_mask = df_rows[merge_key].astype(str).isin(flagged_values)
        else:
            # Se não achar chave, tenta inferir por índice (último recurso)
            if "index" in df_rows_flagged.columns:
                try:
                    idxs = set(pd.to_numeric(df_rows_flagged["index"], errors="coerce").dropna().astype(int).tolist())
                    flagged_mask = df_rows.index.isin(idxs)
                except Exception:
                    pass

    # (4a) Scatter tempo vs missing_pct (destacando flagged)
    df_sc = df_rows.copy()
    df_sc["missing_pct_num"] = pd.to_numeric(df_sc["missing_pct"], errors="coerce")
    df_sc = df_sc.dropna(subset=["missing_pct_num"])

    plt.figure(figsize=(11, 4.5))
    plt.scatter(df_sc.loc[~flagged_mask, "_t"], df_sc.loc[~flagged_mask, "missing_pct_num"], marker="o", label="Linhas")
    if flagged_mask.any():
        plt.scatter(df_sc.loc[flagged_mask, "_t"], df_sc.loc[flagged_mask, "missing_pct_num"], marker="x", label="Flagged")
    plt.title("Missing por observação ao longo do tempo")
    plt.xlabel(time_col)
    plt.ylabel("Missing (%)" if pct_is_0_100 else "Missing (fração)")
    plt.xticks(rotation=45, ha="right")
    plt.legend()
    _savefig(out_dir / "04a_rows_missing_scatter_flagged.png")

    # (4b) Ranking Top N piores linhas (barh)
    df_rank = df_sc.sort_values("missing_pct_num", ascending=False).head(top_n).copy()

    # label do eixo y: tenta usar time_col, senão o índice
    if time_col in df_rows.columns:
        labels = df_rank[time_col].astype(str).tolist()
    else:
        labels = df_rank.index.astype(str).tolist()

    plt.figure(figsize=(10.5, 6))
    plt.barh(labels, df_rank["missing_pct_num"])
    plt.gca().invert_yaxis()
    plt.title(f"Top {top_n} observações com maior missing_pct")
    plt.xlabel("Missing (%)" if pct_is_0_100 else "Missing (fração)")
    plt.ylabel("Observação (tempo / id)")
    _savefig(out_dir / "04b_top_rows_missing_pct.png")


# -----------------------------
# Main
# -----------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Gera plots de missingness (análises 1-4).")
    ap.add_argument("--input-dir", type=str, default=".", help="Diretório onde estão os CSVs (default: .)")
    ap.add_argument("--out-dir", type=str, default="plots_missing", help="Diretório de saída dos plots")
    ap.add_argument("--top-n", type=int, default=20, help="Top N para rankings (default: 20)")

    ap.add_argument("--missing-by-period", type=str, default="missing_by_period.csv")
    ap.add_argument("--missing-by-column", type=str, default="missing_by_column.csv")
    ap.add_argument("--missing-rows", type=str, default="missing_rows.csv")
    ap.add_argument("--rows-flagged", type=str, default="rows_flagged.csv")

    ap.add_argument("--show", action="store_true", help="Mostra os gráficos na tela (além de salvar).")

    args = ap.parse_args()

    in_dir = Path(args.input_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Ler inputs
    df_period = _read_csv(in_dir / args.missing_by_period)
    df_col = _read_csv(in_dir / args.missing_by_column)
    df_rows = _read_csv(in_dir / args.missing_rows)

    df_rows_flagged = None
    rows_flagged_path = in_dir / args.rows_flagged
    if rows_flagged_path.exists():
        df_rows_flagged = _read_csv(rows_flagged_path)

    # Gerar plots
    plots_by_period(df_period, out_dir)
    plots_by_column(df_col, out_dir, top_n=args.top_n)
    plots_by_rows(df_rows, df_rows_flagged, out_dir, top_n=args.top_n)

    print(f"[OK] Plots salvos em: {out_dir.resolve()}")

    if args.show:
        # Se --show foi passado, reabrir rapidamente (opcional).
        # Como já salvamos e fechamos as figuras, apenas avisamos.
        print("[INFO] '--show' foi solicitado, mas os plots foram salvos e fechados. "
              "Abra os PNGs no diretório de saída.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
