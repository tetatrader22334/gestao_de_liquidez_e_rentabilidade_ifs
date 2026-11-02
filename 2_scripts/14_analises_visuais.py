#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Gera análises visuais diretamente a partir da base_un_ajustada.xlsx.

Esta versão adapta o fluxo anterior, que dependia de arquivos intermediários
(estatisticas_numericas.csv, missing.csv, matriz_correlacao.csv etc.), para ler
uma base tabular completa em Excel/CSV e calcular internamente:

1. Estatísticas descritivas de variáveis numéricas;
2. Resumo de variáveis categóricas;
3. Percentual de valores ausentes;
4. Matriz de correlação;
5. Gráficos em PNG na pasta de saída.

Uso recomendado para a base anexada:

python 14_analises_visuais.py --input bases/base_un_ajustada.xlsx --sheet base_corrigida --output-dir outputs/analises_visuais

Dependências:
- pandas
- numpy
- matplotlib
- openpyxl, quando a entrada for .xlsx
"""

from __future__ import annotations

import argparse
import math
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Sequence

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable


SPECTRAL_CMAP = plt.get_cmap("Spectral")
CORR_CMAP = plt.get_cmap("RdBu_r")


# =========================
# Utilitários gerais
# =========================


def ensure_output_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_filename(name: str) -> str:
    invalid = '<>:"/\\|?*'
    cleaned = "".join("_" if ch in invalid else ch for ch in str(name))
    return cleaned.strip().replace(" ", "_")


def normalize_bounds(values: pd.Series | np.ndarray, default_min: float = 0.0, default_max: float = 1.0) -> tuple[float, float]:
    """Retorna limites seguros para Normalize, evitando vmin == vmax."""
    arr = pd.to_numeric(pd.Series(values), errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if arr.empty:
        return default_min, default_max
    vmin = float(arr.min())
    vmax = float(arr.max())
    if math.isclose(vmin, vmax, rel_tol=1e-12, abs_tol=1e-12):
        vmax = vmin + 1.0
    return vmin, vmax


def safe_numeric(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def minmax_series(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    smin = s.min(skipna=True)
    smax = s.max(skipna=True)
    if pd.isna(smin) or pd.isna(smax) or math.isclose(float(smin), float(smax), rel_tol=1e-12, abs_tol=1e-12):
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - smin) / (smax - smin)


def maybe_set_index_from_first_column(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    first_col = str(df.columns[0])
    if first_col.lower().startswith("unnamed"):
        return df.rename(columns={df.columns[0]: "variavel"}).set_index("variavel")
    if "variavel" in df.columns:
        return df.set_index("variavel")
    return df


def first_mode(series: pd.Series) -> object:
    mode_values = series.dropna().mode()
    if mode_values.empty:
        return np.nan
    return mode_values.iloc[0]


def count_modes(series: pd.Series) -> int:
    clean = series.dropna()
    if clean.empty:
        return 0
    counts = clean.value_counts(dropna=True)
    if counts.empty:
        return 0
    return int((counts == counts.max()).sum())


def try_read_csv(path: Path) -> pd.DataFrame:
    """Lê CSV tentando separadores comuns e preservando acentuação."""
    last_error = None
    for sep in [",", ";", None]:
        try:
            if sep is None:
                return pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig")
            return pd.read_csv(path, sep=sep, encoding="utf-8-sig")
        except Exception as exc:  # robustez de leitura
            last_error = exc
    raise RuntimeError(f"Não foi possível ler o arquivo CSV: {path}") from last_error


def read_input_table(path: Path, sheet: Optional[str | int] = None) -> tuple[pd.DataFrame, str]:
    """Lê Excel/CSV e retorna DataFrame + nome da aba/fonte."""
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de entrada não encontrado: {path}")

    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        xls = pd.ExcelFile(path)
        if sheet is None:
            sheet_to_read: str | int = xls.sheet_names[0]
        else:
            # Permite passar índice da aba como texto: --sheet 0
            if isinstance(sheet, str) and sheet.isdigit():
                idx = int(sheet)
                if idx < 0 or idx >= len(xls.sheet_names):
                    raise ValueError(f"Índice de aba inválido: {idx}. Abas disponíveis: {xls.sheet_names}")
                sheet_to_read = xls.sheet_names[idx]
            else:
                sheet_to_read = sheet
            if sheet_to_read not in xls.sheet_names:
                raise ValueError(f"Aba '{sheet_to_read}' não encontrada. Abas disponíveis: {xls.sheet_names}")
        df = pd.read_excel(path, sheet_name=sheet_to_read)
        return df, str(sheet_to_read)

    if suffix == ".csv":
        return try_read_csv(path), "csv"

    if suffix == ".parquet":
        return pd.read_parquet(path), "parquet"

    raise ValueError(
        f"Formato não suportado: {suffix}. Use .xlsx, .xlsm, .xls, .csv ou .parquet."
    )


# =========================
# Cálculo das tabelas-base
# =========================


def compute_missing_table(df: pd.DataFrame) -> pd.DataFrame:
    n = len(df)
    missing = df.isna().sum()
    return pd.DataFrame(
        {
            "variavel": df.columns.astype(str),
            "n_observacoes": n,
            "missing": [int(missing[col]) for col in df.columns],
            "missing_pct": [float(missing[col] / n * 100) if n else 0.0 for col in df.columns],
            "nao_missing": [int(n - missing[col]) for col in df.columns],
            "completude_pct": [float((n - missing[col]) / n * 100) if n else 0.0 for col in df.columns],
        }
    )


def compute_numeric_statistics(df: pd.DataFrame) -> pd.DataFrame:
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    rows: list[dict[str, object]] = []

    for col in numeric_cols:
        s = pd.to_numeric(df[col], errors="coerce")
        n_total = len(s)
        n_missing = int(s.isna().sum())
        clean = s.dropna()
        q = clean.quantile([0.25, 0.50, 0.75]) if not clean.empty else pd.Series([np.nan, np.nan, np.nan], index=[0.25, 0.50, 0.75])

        rows.append(
            {
                "variavel": col,
                "tipo": str(df[col].dtype),
                "n_observacoes": n_total,
                "n_validos": int(clean.shape[0]),
                "missing": n_missing,
                "missing_pct": float(n_missing / n_total * 100) if n_total else 0.0,
                "media": float(clean.mean()) if not clean.empty else np.nan,
                "moda": first_mode(clean),
                "qtd_modas": count_modes(clean),
                "mediana": float(clean.median()) if not clean.empty else np.nan,
                "desvio_padrao": float(clean.std(ddof=1)) if clean.shape[0] > 1 else np.nan,
                "variancia": float(clean.var(ddof=1)) if clean.shape[0] > 1 else np.nan,
                "minimo": float(clean.min()) if not clean.empty else np.nan,
                "q1": float(q.loc[0.25]) if not clean.empty else np.nan,
                "q2": float(q.loc[0.50]) if not clean.empty else np.nan,
                "q3": float(q.loc[0.75]) if not clean.empty else np.nan,
                "maximo": float(clean.max()) if not clean.empty else np.nan,
                "assimetria": float(clean.skew()) if clean.shape[0] > 2 else np.nan,
                "curtose": float(clean.kurt()) if clean.shape[0] > 3 else np.nan,
                "n_unicos": int(clean.nunique(dropna=True)),
            }
        )

    return pd.DataFrame(rows)


def compute_categorical_statistics(df: pd.DataFrame) -> pd.DataFrame:
    categorical_cols = [col for col in df.columns if not pd.api.types.is_numeric_dtype(df[col])]
    rows: list[dict[str, object]] = []

    for col in categorical_cols:
        s = df[col]
        n_total = len(s)
        n_missing = int(s.isna().sum())
        clean = s.dropna()
        counts = clean.value_counts(dropna=True)
        freq_moda = int(counts.iloc[0]) if not counts.empty else 0
        rows.append(
            {
                "variavel": col,
                "tipo": str(df[col].dtype),
                "n_observacoes": n_total,
                "n_validos": int(clean.shape[0]),
                "missing": n_missing,
                "missing_pct": float(n_missing / n_total * 100) if n_total else 0.0,
                "n_unicos": int(clean.nunique(dropna=True)),
                "moda": first_mode(clean),
                "qtd_modas": count_modes(clean),
                "freq_moda": freq_moda,
                "pct_moda": float(freq_moda / clean.shape[0] * 100) if clean.shape[0] else 0.0,
            }
        )

    return pd.DataFrame(rows)


def compute_correlation_matrix(
    df: pd.DataFrame,
    method: str = "pearson",
    min_non_null: int = 3,
    exclude_cols: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    exclude = set(exclude_cols or [])
    numeric_cols = [col for col in df.select_dtypes(include=[np.number]).columns if col not in exclude]

    valid_cols = []
    for col in numeric_cols:
        s = pd.to_numeric(df[col], errors="coerce")
        if s.notna().sum() >= min_non_null and s.nunique(dropna=True) > 1:
            valid_cols.append(col)

    if not valid_cols:
        return pd.DataFrame()

    return df[valid_cols].corr(method=method)


def build_metadata_table(
    input_path: Path,
    sheet_name: str,
    df: pd.DataFrame,
    numeric_df: pd.DataFrame,
    categorical_df: pd.DataFrame,
    corr_df: pd.DataFrame,
    corr_method: str,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"item": "arquivo_entrada", "valor": str(input_path)},
            {"item": "aba_ou_fonte", "valor": sheet_name},
            {"item": "linhas", "valor": int(df.shape[0])},
            {"item": "colunas", "valor": int(df.shape[1])},
            {"item": "variaveis_numericas", "valor": int(len(numeric_df))},
            {"item": "variaveis_categoricas", "valor": int(len(categorical_df))},
            {"item": "variaveis_na_correlacao", "valor": int(corr_df.shape[0]) if not corr_df.empty else 0},
            {"item": "metodo_correlacao", "valor": corr_method},
            {"item": "gerado_em", "valor": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        ]
    )


def save_analysis_tables(
    output_dir: Path,
    numeric_df: pd.DataFrame,
    categorical_df: pd.DataFrame,
    missing_df: pd.DataFrame,
    corr_df: pd.DataFrame,
    metadata_df: pd.DataFrame,
) -> None:
    numeric_df.to_csv(output_dir / "estatisticas_numericas.csv", index=False, encoding="utf-8-sig")
    categorical_df.to_csv(output_dir / "estatisticas_categoricas.csv", index=False, encoding="utf-8-sig")
    missing_df.to_csv(output_dir / "missing.csv", index=False, encoding="utf-8-sig")
    metadata_df.to_csv(output_dir / "metadados.csv", index=False, encoding="utf-8-sig")
    if not corr_df.empty:
        corr_df.to_csv(output_dir / "matriz_correlacao.csv", index=True, index_label="variavel", encoding="utf-8-sig")
    else:
        pd.DataFrame().to_csv(output_dir / "matriz_correlacao.csv", index=False, encoding="utf-8-sig")


# =========================
# Gráficos
# =========================


def save_metadata_table(metadata_df: pd.DataFrame, output_file: Path) -> None:
    if metadata_df.empty:
        return

    fig, ax = plt.subplots(figsize=(11, max(3, 0.55 * len(metadata_df) + 1.5)))
    ax.axis("off")
    ax.set_title("Metadados da análise", fontsize=14, pad=14)

    table = ax.table(
        cellText=metadata_df.values,
        colLabels=list(metadata_df.columns),
        cellLoc="left",
        colLoc="left",
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.4)

    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_facecolor(SPECTRAL_CMAP(0.15))
            cell.set_text_props(weight="bold", color="black")
        else:
            cell.set_facecolor(SPECTRAL_CMAP(0.85 if row % 2 else 0.75))

    fig.tight_layout()
    fig.savefig(output_file, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_missing(missing_df: pd.DataFrame, output_file: Path, top_n: int = 30) -> None:
    df = missing_df.copy()
    if df.empty or "missing_pct" not in df.columns:
        return

    df = safe_numeric(df, ["missing", "missing_pct", "n_observacoes"])
    df = df.sort_values(["missing_pct", "missing"], ascending=[False, False]).head(top_n)
    if df.empty:
        return
    df = df.iloc[::-1]

    vals = df["missing_pct"].fillna(0)
    vmin, vmax = normalize_bounds(vals)
    norm = Normalize(vmin=vmin, vmax=vmax)
    colors = [SPECTRAL_CMAP(norm(v)) for v in vals]

    fig, ax = plt.subplots(figsize=(12, max(6, 0.35 * len(df) + 2)))
    bars = ax.barh(df["variavel"], vals, color=colors, edgecolor="black", linewidth=0.4)
    ax.set_title(f"Top {min(top_n, len(df))} variáveis por percentual de missing", fontsize=14)
    ax.set_xlabel("Missing (%)")
    ax.set_ylabel("Variável")
    ax.grid(axis="x", alpha=0.25)

    x_offset = max(0.8, float(vals.max()) * 0.02 if len(vals) else 0.8)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_width() + x_offset, bar.get_y() + bar.get_height() / 2, f"{val:.1f}%", va="center", fontsize=8)

    sm = ScalarMappable(norm=norm, cmap=SPECTRAL_CMAP)
    cbar = fig.colorbar(sm, ax=ax)
    cbar.set_label("Intensidade do missing (%)")

    fig.tight_layout()
    fig.savefig(output_file, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_numeric_heatmap(numeric_df: pd.DataFrame, output_file: Path, top_n: int = 25) -> None:
    df = numeric_df.copy()
    if df.empty:
        return

    metric_cols = [
        "media", "mediana", "desvio_padrao", "minimo", "q1", "q2", "q3", "maximo", "missing_pct"
    ]
    df = safe_numeric(df, metric_cols)

    if "desvio_padrao" in df.columns:
        selection = df.sort_values("desvio_padrao", ascending=False, na_position="last").head(top_n).copy()
    else:
        selection = df.head(top_n).copy()

    if selection.empty:
        return

    available_metrics = [c for c in metric_cols if c in selection.columns]
    if not available_metrics:
        return

    heat = selection[available_metrics].copy()
    for col in heat.columns:
        heat[col] = minmax_series(heat[col])
    heat = heat.fillna(0)

    fig_h = max(6, 0.36 * len(heat) + 2)
    fig_w = max(10, 0.95 * len(heat.columns) + 3)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    im = ax.imshow(heat.values, aspect="auto", cmap=SPECTRAL_CMAP, interpolation="nearest")

    ax.set_title("Estatísticas descritivas normalizadas (maior desvio-padrão)", fontsize=14)
    ax.set_xticks(np.arange(len(heat.columns)))
    ax.set_xticklabels(heat.columns, rotation=45, ha="right")
    ax.set_yticks(np.arange(len(heat.index)))
    ax.set_yticklabels(selection["variavel"])

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Escala min-max por métrica")

    fig.tight_layout()
    fig.savefig(output_file, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_mean_vs_median(numeric_df: pd.DataFrame, output_file: Path, annotate_n: int = 12) -> None:
    df = numeric_df.copy()
    if df.empty:
        return

    df = safe_numeric(df, ["media", "mediana", "desvio_padrao", "missing_pct"])
    df = df.dropna(subset=["media", "mediana"])
    if df.empty:
        return

    # Padronização por ranking percentual para evitar explosão de escala entre variáveis financeiras.
    x = df["mediana"].rank(pct=True)
    y = df["media"].rank(pct=True)
    color_metric = df["desvio_padrao"].rank(pct=True).fillna(0)
    sizes = 70 + 240 * (1 - df["missing_pct"].fillna(0).clip(lower=0, upper=100) / 100)

    fig, ax = plt.subplots(figsize=(10, 8))
    scatter = ax.scatter(x, y, c=color_metric, s=sizes, cmap=SPECTRAL_CMAP, alpha=0.85, edgecolor="black", linewidth=0.4)

    ax.plot([0, 1], [0, 1], linestyle="--", linewidth=1.1, color="gray", alpha=0.8)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel("Ranking percentual da mediana")
    ax.set_ylabel("Ranking percentual da média")
    ax.set_title("Média vs. mediana por variável (cor = desvio-padrão; tamanho = completude)", fontsize=14)
    ax.grid(alpha=0.25)

    df = df.assign(rank_diff=(y - x).abs(), x=x, y=y)
    labels = df.nlargest(min(annotate_n, len(df)), "rank_diff")
    for _, row in labels.iterrows():
        ax.annotate(
            row["variavel"],
            (row["x"], row["y"]),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8,
            alpha=0.9,
        )

    cbar = fig.colorbar(scatter, ax=ax)
    cbar.set_label("Ranking percentual do desvio-padrão")

    fig.tight_layout()
    fig.savefig(output_file, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_range_iqr(numeric_df: pd.DataFrame, output_file: Path, top_n: int = 20) -> None:
    df = numeric_df.copy()
    if df.empty:
        return

    metric_cols = ["minimo", "q1", "mediana", "q3", "maximo"]
    df = safe_numeric(df, metric_cols)
    if not set(metric_cols).issubset(df.columns):
        return

    df["iqr"] = df["q3"] - df["q1"]
    df = df.dropna(subset=["minimo", "q1", "mediana", "q3", "maximo", "iqr"])
    df = df.sort_values("iqr", ascending=False).head(top_n)
    if df.empty:
        return

    fig, ax = plt.subplots(figsize=(13, max(6, 0.42 * len(df) + 2)))
    y_positions = np.arange(len(df))
    vmin, vmax = normalize_bounds(df["iqr"])
    norm = Normalize(vmin=vmin, vmax=vmax)

    for y, (_, row) in zip(y_positions, df.iterrows()):
        color = SPECTRAL_CMAP(norm(row["iqr"]))
        ax.hlines(y, row["minimo"], row["maximo"], color="lightgray", linewidth=2.0, zorder=1)
        ax.hlines(y, row["q1"], row["q3"], color=color, linewidth=7.0, zorder=2)
        ax.plot(row["mediana"], y, marker="o", markersize=6, color="black", zorder=3)

    ax.set_yticks(y_positions)
    ax.set_yticklabels(df["variavel"])
    ax.set_title("Amplitude total e intervalo interquartílico (IQR)", fontsize=14)
    ax.set_xlabel("Escala original da variável")
    ax.set_ylabel("Variável")
    ax.grid(axis="x", alpha=0.25)

    sm = ScalarMappable(norm=norm, cmap=SPECTRAL_CMAP)
    cbar = fig.colorbar(sm, ax=ax)
    cbar.set_label("IQR")

    fig.tight_layout()
    fig.savefig(output_file, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_correlation_heatmap(corr_df: pd.DataFrame, output_file: Path, max_vars: int = 35) -> None:
    df = corr_df.copy()
    df = maybe_set_index_from_first_column(df)
    df = df.apply(pd.to_numeric, errors="coerce")

    if df.empty:
        return

    # Remove linhas/colunas totalmente vazias, comuns quando há variáveis constantes.
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    if df.empty:
        return

    # Para legibilidade, prioriza variáveis com maior correlação média absoluta.
    if df.shape[0] > max_vars:
        mean_abs_corr = df.abs().mean(axis=1).sort_values(ascending=False)
        keep = mean_abs_corr.head(max_vars).index
        df = df.loc[keep, keep]

    fig_size = max(10, 0.34 * len(df) + 3)
    fig, ax = plt.subplots(figsize=(fig_size, fig_size))
    im = ax.imshow(df.values, cmap=CORR_CMAP, vmin=-1, vmax=1, aspect="auto", interpolation="nearest")
    ax.set_title("Matriz de correlação", fontsize=14)
    ax.set_xticks(np.arange(len(df.columns)))
    ax.set_xticklabels(df.columns, rotation=90, fontsize=8)
    ax.set_yticks(np.arange(len(df.index)))
    ax.set_yticklabels(df.index, fontsize=8)

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Correlação")

    fig.tight_layout()
    fig.savefig(output_file, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_top_correlations(corr_df: pd.DataFrame, output_file: Path, top_n: int = 20) -> None:
    df = corr_df.copy()
    df = maybe_set_index_from_first_column(df)
    df = df.apply(pd.to_numeric, errors="coerce")
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    if df.empty:
        return

    # Garante alinhamento quadrado caso venha de CSV editado manualmente.
    common = [c for c in df.columns if c in df.index]
    if common:
        df = df.loc[common, common]

    mask = np.triu(np.ones(df.shape, dtype=bool), k=1)
    pairs = []
    for i, row_name in enumerate(df.index):
        for j, col_name in enumerate(df.columns):
            if mask[i, j] and pd.notna(df.iat[i, j]):
                corr_value = float(df.iat[i, j])
                pairs.append((f"{row_name} × {col_name}", corr_value, abs(corr_value)))

    if not pairs:
        return

    pair_df = pd.DataFrame(pairs, columns=["par", "corr", "abs_corr"])
    pair_df = pair_df.sort_values("abs_corr", ascending=False).head(top_n)
    pair_df = pair_df.iloc[::-1]

    norm = Normalize(vmin=-1, vmax=1)
    colors = [CORR_CMAP(norm(v)) for v in pair_df["corr"]]

    fig, ax = plt.subplots(figsize=(13, max(6, 0.42 * len(pair_df) + 2)))
    bars = ax.barh(pair_df["par"], pair_df["corr"], color=colors, edgecolor="black", linewidth=0.4)
    ax.axvline(0, color="black", linewidth=1)
    ax.set_title(f"Top {min(top_n, len(pair_df))} correlações absolutas", fontsize=14)
    ax.set_xlabel("Coeficiente de correlação")
    ax.set_ylabel("Par de variáveis")
    ax.grid(axis="x", alpha=0.25)

    for bar, val in zip(bars, pair_df["corr"]):
        x = val + 0.02 if val >= 0 else val - 0.02
        ha = "left" if val >= 0 else "right"
        ax.text(x, bar.get_y() + bar.get_height() / 2, f"{val:.2f}", va="center", ha=ha, fontsize=8)

    fig.tight_layout()
    fig.savefig(output_file, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_categorical_summary(categorical_df: pd.DataFrame, output_file: Path, top_n: int = 30) -> None:
    df = categorical_df.copy()
    if df.empty:
        return

    df = safe_numeric(df, ["n_observacoes", "missing", "missing_pct", "qtd_modas", "n_unicos"])
    df = df.sort_values("n_unicos", ascending=False).head(top_n)
    if df.empty:
        return
    df = df.iloc[::-1]

    vals = df["n_unicos"].fillna(0)
    vmin, vmax = normalize_bounds(vals)
    norm = Normalize(vmin=vmin, vmax=vmax)
    colors = [SPECTRAL_CMAP(norm(v)) for v in vals]

    fig, ax = plt.subplots(figsize=(10, max(4, 0.6 * len(df) + 2)))
    bars = ax.barh(df["variavel"], vals, color=colors, edgecolor="black", linewidth=0.4)
    ax.set_title("Número de categorias únicas por variável categórica", fontsize=14)
    ax.set_xlabel("n_unicos")
    ax.set_ylabel("Variável")
    ax.grid(axis="x", alpha=0.25)

    for bar, val in zip(bars, vals):
        ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2, f"{int(val)}", va="center", fontsize=8)

    fig.tight_layout()
    fig.savefig(output_file, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_data_completeness(missing_df: pd.DataFrame, output_file: Path, top_n: int = 30) -> None:
    df = missing_df.copy()
    if df.empty:
        return

    if "completude_pct" not in df.columns:
        df = safe_numeric(df, ["missing_pct"])
        df["completude_pct"] = 100 - df["missing_pct"].fillna(100)
    else:
        df = safe_numeric(df, ["completude_pct"])

    df = df.sort_values("completude_pct", ascending=True).head(top_n)
    if df.empty:
        return
    df = df.iloc[::-1]

    vals = df["completude_pct"].fillna(0)
    vmin, vmax = normalize_bounds(vals)
    norm = Normalize(vmin=vmin, vmax=vmax)
    colors = [SPECTRAL_CMAP(norm(v)) for v in vals]

    fig, ax = plt.subplots(figsize=(12, max(6, 0.35 * len(df) + 2)))
    bars = ax.barh(df["variavel"], vals, color=colors, edgecolor="black", linewidth=0.4)
    ax.set_title(f"Completude das {min(top_n, len(df))} variáveis menos completas", fontsize=14)
    ax.set_xlabel("Completude (%)")
    ax.set_ylabel("Variável")
    ax.grid(axis="x", alpha=0.25)

    x_offset = max(0.8, float(vals.max()) * 0.02 if len(vals) else 0.8)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_width() + x_offset, bar.get_y() + bar.get_height() / 2, f"{val:.1f}%", va="center", fontsize=8)

    fig.tight_layout()
    fig.savefig(output_file, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_variable_type_summary(numeric_df: pd.DataFrame, categorical_df: pd.DataFrame, output_file: Path) -> None:
    labels = ["Numéricas", "Categóricas"]
    vals = [len(numeric_df), len(categorical_df)]
    if sum(vals) == 0:
        return

    vmin, vmax = normalize_bounds(pd.Series(vals))
    norm = Normalize(vmin=vmin, vmax=vmax)
    colors = [SPECTRAL_CMAP(norm(v)) for v in vals]

    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(labels, vals, color=colors, edgecolor="black", linewidth=0.5)
    ax.set_title("Distribuição de tipos de variáveis", fontsize=14)
    ax.set_ylabel("Quantidade de variáveis")
    ax.grid(axis="y", alpha=0.25)

    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2, str(val), ha="center", va="bottom", fontsize=10)

    fig.tight_layout()
    fig.savefig(output_file, dpi=220, bbox_inches="tight")
    plt.close(fig)


# =========================
# Pipeline principal
# =========================


def comma_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gera análises visuais diretamente da base_un_ajustada ou de outra base tabular."
    )
    parser.add_argument("--input", default="base_un_ajustada.xlsx", help="Arquivo de entrada: .xlsx, .csv ou .parquet")
    parser.add_argument("--sheet", default=None, help="Nome ou índice da aba quando a entrada for Excel. Ex.: base_corrigida ou 0")
    parser.add_argument("--output-dir", default="analises_visuais_base_un_ajustada", help="Diretório de saída dos gráficos e tabelas")
    parser.add_argument(
        "--corr-method",
        choices=["pearson", "spearman", "kendall"],
        default="pearson",
        help="Método de correlação. Pearson é o padrão.",
    )
    parser.add_argument(
        "--exclude-corr",
        default="",
        help="Lista de colunas numéricas a excluir da matriz de correlação, separadas por vírgula. Ex.: AnoMes_ord,trimestre",
    )
    parser.add_argument("--top-missing", type=int, default=30, help="Número de variáveis no gráfico de missing")
    parser.add_argument("--top-heatmap", type=int, default=25, help="Número de variáveis no heatmap de estatísticas")
    parser.add_argument("--top-iqr", type=int, default=20, help="Número de variáveis no gráfico de IQR")
    parser.add_argument("--top-corr", type=int, default=20, help="Número de pares no gráfico de maiores correlações")
    parser.add_argument("--max-corr-vars", type=int, default=35, help="Número máximo de variáveis no heatmap de correlação")
    return parser


def write_manifest(output_dir: Path, input_path: Path, sheet_name: str) -> None:
    manifest = output_dir / "README.txt"
    manifest.write_text(
        "\n".join(
            [
                "Análises visuais geradas a partir da base tabular.",
                f"Arquivo de entrada: {input_path}",
                f"Aba/fonte: {sheet_name}",
                "",
                "Tabelas geradas:",
                "estatisticas_numericas.csv - estatísticas descritivas das variáveis numéricas",
                "estatisticas_categoricas.csv - resumo das variáveis categóricas",
                "missing.csv - contagem e percentual de dados ausentes por variável",
                "matriz_correlacao.csv - matriz de correlação das variáveis numéricas válidas",
                "metadados.csv - metadados da execução",
                "",
                "Gráficos gerados:",
                "01_missing_top_variaveis.png - maior percentual de missing",
                "02_completude_variaveis.png - variáveis menos completas",
                "03_heatmap_estatisticas_normalizadas.png - estatísticas descritivas normalizadas",
                "04_media_vs_mediana.png - média vs. mediana com desvio-padrão e completude",
                "05_amplitude_e_iqr.png - amplitude total e IQR",
                "06_matriz_correlacao_heatmap.png - heatmap da correlação",
                "07_top_correlacoes.png - maiores correlações absolutas",
                "08_resumo_categoricas.png - resumo das variáveis categóricas, se houver",
                "09_metadados.png - tabela com metadados da análise",
                "10_tipos_variaveis.png - quantidade de variáveis numéricas e categóricas",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    args = build_parser().parse_args()

    input_path = Path(args.input)
    output_dir = ensure_output_dir(Path(args.output_dir))
    exclude_corr = comma_list(args.exclude_corr)

    print(f"Lendo base: {input_path}")
    df, sheet_name = read_input_table(input_path, sheet=args.sheet)

    # Remove colunas completamente vazias, frequentes em planilhas exportadas.
    empty_cols = [col for col in df.columns if df[col].isna().all()]
    if empty_cols:
        print(f"Removendo {len(empty_cols)} coluna(s) totalmente vazia(s).")
        df = df.drop(columns=empty_cols)

    print(f"Base carregada: {df.shape[0]} linhas × {df.shape[1]} colunas | aba/fonte: {sheet_name}")

    print("Calculando estatísticas, missing values e matriz de correlação...")
    missing_df = compute_missing_table(df)
    numeric_df = compute_numeric_statistics(df)
    categorical_df = compute_categorical_statistics(df)
    corr_df = compute_correlation_matrix(df, method=args.corr_method, exclude_cols=exclude_corr)
    metadata_df = build_metadata_table(
        input_path=input_path,
        sheet_name=sheet_name,
        df=df,
        numeric_df=numeric_df,
        categorical_df=categorical_df,
        corr_df=corr_df,
        corr_method=args.corr_method,
    )

    print("Salvando tabelas intermediárias...")
    save_analysis_tables(output_dir, numeric_df, categorical_df, missing_df, corr_df, metadata_df)

    print("Gerando gráficos...")
    plot_missing(missing_df, output_dir / "01_missing_top_variaveis.png", top_n=args.top_missing)
    plot_data_completeness(missing_df, output_dir / "02_completude_variaveis.png", top_n=args.top_missing)
    plot_numeric_heatmap(numeric_df, output_dir / "03_heatmap_estatisticas_normalizadas.png", top_n=args.top_heatmap)
    plot_mean_vs_median(numeric_df, output_dir / "04_media_vs_mediana.png")
    plot_range_iqr(numeric_df, output_dir / "05_amplitude_e_iqr.png", top_n=args.top_iqr)
    plot_correlation_heatmap(corr_df, output_dir / "06_matriz_correlacao_heatmap.png", max_vars=args.max_corr_vars)
    plot_top_correlations(corr_df, output_dir / "07_top_correlacoes.png", top_n=args.top_corr)
    plot_categorical_summary(categorical_df, output_dir / "08_resumo_categoricas.png")
    save_metadata_table(metadata_df, output_dir / "09_metadados.png")
    plot_variable_type_summary(numeric_df, categorical_df, output_dir / "10_tipos_variaveis.png")

    write_manifest(output_dir, input_path, sheet_name)

    print(f"Concluído. Saídas salvas em: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
