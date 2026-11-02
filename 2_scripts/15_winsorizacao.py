#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
winsorizacao_outliers_base.py

Script para winsorização e tratamento de outliers em bases de painel financeiro/bancário.

Características principais
--------------------------
1. Lê bases .xlsx, .xls, .csv ou .parquet.
2. Preserva, por padrão, identificadores, variáveis temporais, dummies, variáveis macroeconômicas
   e medidas estruturais de concentração/market share.
3. Trata variáveis numéricas contínuas com estratégia conservadora ou ampla.
4. Permite winsorização global ou por grupos, por exemplo por AnoMes_ord.
5. Gera flags de outlier e relatório detalhado de limites, quantidade de caps e percentuais alterados.
6. Permite calcular os limites apenas no conjunto de treino via --fit-query, reduzindo risco de leakage.

python 15_winsorizacao.py --input bases/base_final.xlsx --sheet base --exclude-cols lcr_dec,nsfr_dec --fit-query "AnoMes_ord <= 202209" --output bases/base_final_winsorizada.xlsx

Observação metodológica
-----------------------
Para dissertações com dados de instituições financeiras, evite winsorizar indiscriminadamente
variáveis monetárias brutas, pois diferenças extremas de escala podem representar heterogeneidade
real entre instituições, não erro. Em geral, priorize razões, percentuais e variáveis já transformadas
em log. Use --strategy all_continuous somente após justificar a escolha.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


# -----------------------------------------------------------------------------
# Configurações padrão ajustadas para base bancária/painel.
# -----------------------------------------------------------------------------
DEFAULT_ID_TIME_PATTERNS = [
    r"^id_", r"id$", r"ticker", r"cnpj", r"cod", r"codigo", r"nome",
    r"^AnoMes", r"ano", r"mes", r"trimestre", r"quarter", r"data", r"date",
]

DEFAULT_MACRO_PATTERNS = [
    r"ipca", r"selic", r"pib", r"cambio", r"dolar", r"juros", r"inflacao",
]

DEFAULT_MARKET_STRUCTURE_PATTERNS = [
    r"hhi", r"market_share", r"concentracao", r"ativos_totais_amostra",
    r"ativos_totais_banco",
]

# Variáveis categóricas/dummies específicas observadas na base.
DEFAULT_ALWAYS_EXCLUDE = [
    "AnoMes_ord", "id_entidade", "trimestre",
    "estatal", "controle_estrangeiro", "crise_nme", "crise_covid",
]


@dataclass
class ColumnReport:
    column: str
    method: str
    strategy: str
    group: Optional[str]
    lower_bound: Optional[float]
    upper_bound: Optional[float]
    n_obs: int
    n_missing: int
    n_below: int
    n_above: int
    n_capped_total: int
    pct_capped_total: float
    mean_before: Optional[float]
    std_before: Optional[float]
    min_before: Optional[float]
    p01_before: Optional[float]
    median_before: Optional[float]
    p99_before: Optional[float]
    max_before: Optional[float]
    mean_after: Optional[float]
    std_after: Optional[float]
    min_after: Optional[float]
    max_after: Optional[float]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Winsorização e tratamento de outliers para base financeira/bancária.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", required=True, help="Arquivo de entrada (.xlsx, .xls, .csv ou .parquet).")
    parser.add_argument("--sheet", default=None, help="Nome da aba no Excel. Se omitido, usa a primeira aba.")
    parser.add_argument("--output", default=None, help="Arquivo de saída. Se omitido, cria *_winsorizada.xlsx.")
    parser.add_argument("--report-csv", default=None, help="Caminho opcional para salvar relatório em CSV.")

    parser.add_argument(
        "--strategy",
        choices=["conservative", "ratios_only", "all_continuous"],
        default="conservative",
        help=(
            "conservative: razões/percentuais/logs, excluindo macro e market structure; "
            "ratios_only: somente razões/percentuais; "
            "all_continuous: todas as numéricas contínuas elegíveis."
        ),
    )
    parser.add_argument(
        "--method",
        choices=["winsor", "iqr_cap", "mad_cap", "zscore_cap", "flag_only", "drop_rows"],
        default="winsor",
        help="Método de tratamento de outliers.",
    )
    parser.add_argument("--lower", type=float, default=0.01, help="Quantil inferior para winsorização.")
    parser.add_argument("--upper", type=float, default=0.99, help="Quantil superior para winsorização.")
    parser.add_argument("--iqr-multiplier", type=float, default=3.0, help="Multiplicador do IQR para iqr_cap/drop_rows.")
    parser.add_argument("--mad-threshold", type=float, default=3.5, help="Limiar robusto para MAD modificado.")
    parser.add_argument("--z-threshold", type=float, default=4.0, help="Limiar para zscore_cap.")

    parser.add_argument(
        "--group-cols",
        default="",
        help="Colunas para tratamento por grupo, separadas por vírgula. Ex.: AnoMes_ord ou id_entidade,AnoMes_ord.",
    )
    parser.add_argument("--min-group-size", type=int, default=10, help="Tamanho mínimo de grupo para calcular limites próprios.")
    parser.add_argument(
        "--fit-query",
        default=None,
        help=(
            "Expressão pandas.DataFrame.query para calcular limites apenas em uma subamostra, "
            "por exemplo: \"AnoMes_ord <= 202112\". Os limites são aplicados em toda a base."
        ),
    )

    parser.add_argument(
        "--include-cols",
        default="",
        help="Lista explícita de colunas a tratar. Se usada, sobrepõe a seleção automática.",
    )
    parser.add_argument(
        "--force-cols",
        default="",
        help="Colunas adicionais a tratar, mesmo que a seleção automática as exclua.",
    )
    parser.add_argument(
        "--exclude-cols",
        default="",
        help="Colunas adicionais a preservar, separadas por vírgula.",
    )
    parser.add_argument("--treat-macro-vars", action="store_true", help="Permite tratar variáveis macroeconômicas.")
    parser.add_argument("--treat-market-vars", action="store_true", help="Permite tratar HHI, market share e variáveis de escala/concentração.")
    parser.add_argument("--no-flags", action="store_true", help="Não cria colunas de flags de outlier na base de saída.")
    parser.add_argument("--flag-prefix", default="flag_outlier__", help="Prefixo das colunas de flags.")
    parser.add_argument("--keep-original-cols", action="store_true", help="Mantém cópias *_orig das colunas tratadas.")
    parser.add_argument("--drop-na-all-targets", action="store_true", help="Remove linhas com NA em todas as colunas tratadas.")
    parser.add_argument("--bounds-json-out", default=None, help="Salva os limites calculados em JSON.")
    parser.add_argument("--bounds-json-in", default=None, help="Usa limites previamente salvos em JSON, sem recalcular.")
    parser.add_argument("--decimal-comma-csv", action="store_true", help="Ao salvar CSV, usa vírgula decimal e separador ';'.")
    parser.add_argument("--dry-run", action="store_true", help="Não salva a base tratada; apenas mostra seleção e relatório.")
    return parser.parse_args()


def split_cols(value: str | Sequence[str] | None) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        raw = []
        for item in value:
            raw.extend(str(item).split(","))
    else:
        raw = re.split(r"[,;]", str(value))
    return [x.strip() for x in raw if x and x.strip()]


def safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        if pd.isna(x):
            return None
        val = float(x)
        if math.isfinite(val):
            return val
        return None
    except Exception:
        return None


def read_input(path: Path, sheet: Optional[str]) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in [".xlsx", ".xlsm", ".xls"]:
        return pd.read_excel(path, sheet_name=sheet if sheet else 0)
    if suffix == ".csv":
        # Tentativa robusta para CSV comum no Brasil e CSV padrão.
        try:
            return pd.read_csv(path, sep=None, engine="python")
        except Exception:
            return pd.read_csv(path, sep=";", decimal=",")
    if suffix == ".parquet":
        return pd.read_parquet(path)
    raise ValueError(f"Formato não suportado: {suffix}")


def is_binary_numeric(series: pd.Series) -> bool:
    if not pd.api.types.is_numeric_dtype(series):
        return False
    vals = pd.Series(series.dropna().unique())
    if vals.empty:
        return False
    return set(vals.astype(float).unique()).issubset({0.0, 1.0})


def matches_any(name: str, patterns: Iterable[str]) -> bool:
    lname = str(name).lower()
    return any(re.search(p, lname, flags=re.IGNORECASE) for p in patterns)


def infer_target_columns(
    df: pd.DataFrame,
    strategy: str,
    include_cols: List[str],
    force_cols: List[str],
    exclude_cols: List[str],
    treat_macro_vars: bool,
    treat_market_vars: bool,
) -> Tuple[List[str], Dict[str, List[str]]]:
    """Seleciona colunas elegíveis para tratamento."""
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    missing_include = [c for c in include_cols + force_cols + exclude_cols if c and c not in df.columns]
    if missing_include:
        raise ValueError(f"Colunas informadas não existem na base: {missing_include}")

    always_exclude = set(DEFAULT_ALWAYS_EXCLUDE).intersection(df.columns)
    always_exclude.update(exclude_cols)

    binary_cols = {c for c in numeric_cols if is_binary_numeric(df[c])}
    id_time_cols = {c for c in df.columns if matches_any(c, DEFAULT_ID_TIME_PATTERNS)}
    macro_cols = {c for c in df.columns if matches_any(c, DEFAULT_MACRO_PATTERNS)}
    market_cols = {c for c in df.columns if matches_any(c, DEFAULT_MARKET_STRUCTURE_PATTERNS)}

    if include_cols:
        selected = [c for c in include_cols if c in numeric_cols]
    else:
        selected = []
        for c in numeric_cols:
            if c in always_exclude or c in binary_cols or c in id_time_cols:
                continue
            if (not treat_macro_vars) and c in macro_cols:
                continue
            if (not treat_market_vars) and c in market_cols:
                continue

            lname = c.lower()
            is_ratio = (
                lname.endswith("_dec") or lname.endswith("_pct") or
                "ratio" in lname or "indice" in lname or
                lname in {"roe_dec", "roe_pct", "roa_dec", "roa_pct", "lcr_dec", "nsfr_dec"}
            )
            is_log = lname.endswith("_log") or "_log_" in lname

            if strategy == "ratios_only" and is_ratio:
                selected.append(c)
            elif strategy == "conservative" and (is_ratio or is_log):
                selected.append(c)
            elif strategy == "all_continuous":
                selected.append(c)

    # Adiciona colunas forçadas no fim, sem duplicidade.
    for c in force_cols:
        if c not in selected and c in numeric_cols:
            selected.append(c)

    # Remove exclusões explícitas novamente, exceto se também foi forçada.
    force_set = set(force_cols)
    selected = [c for c in selected if (c not in always_exclude or c in force_set)]

    diagnostics = {
        "numeric_cols": numeric_cols,
        "selected_cols": selected,
        "excluded_always": sorted(always_exclude),
        "excluded_binary": sorted(binary_cols),
        "excluded_id_time": sorted(id_time_cols),
        "excluded_macro": sorted(macro_cols) if not treat_macro_vars else [],
        "excluded_market_structure": sorted(market_cols) if not treat_market_vars else [],
    }
    return selected, diagnostics


def finite_series(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    s = s.replace([np.inf, -np.inf], np.nan)
    return s


def quantile_bounds(s: pd.Series, lower: float, upper: float) -> Tuple[Optional[float], Optional[float]]:
    s = finite_series(s).dropna()
    if s.empty:
        return None, None
    if not (0 <= lower < upper <= 1):
        raise ValueError("É necessário que 0 <= lower < upper <= 1.")
    return safe_float(s.quantile(lower)), safe_float(s.quantile(upper))


def iqr_bounds(s: pd.Series, multiplier: float) -> Tuple[Optional[float], Optional[float]]:
    s = finite_series(s).dropna()
    if s.empty:
        return None, None
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    return safe_float(q1 - multiplier * iqr), safe_float(q3 + multiplier * iqr)


def mad_bounds(s: pd.Series, threshold: float) -> Tuple[Optional[float], Optional[float]]:
    s = finite_series(s).dropna()
    if s.empty:
        return None, None
    med = s.median()
    mad = np.median(np.abs(s - med))
    if mad == 0 or pd.isna(mad):
        # fallback robusto: sem dispersão pelo MAD, usa IQR conservador.
        return iqr_bounds(s, multiplier=3.0)
    robust_sigma = 1.4826 * mad
    return safe_float(med - threshold * robust_sigma), safe_float(med + threshold * robust_sigma)


def zscore_bounds(s: pd.Series, threshold: float) -> Tuple[Optional[float], Optional[float]]:
    s = finite_series(s).dropna()
    if s.empty:
        return None, None
    mu = s.mean()
    sd = s.std(ddof=0)
    if sd == 0 or pd.isna(sd):
        return safe_float(mu), safe_float(mu)
    return safe_float(mu - threshold * sd), safe_float(mu + threshold * sd)


def compute_bounds_for_series(
    s: pd.Series,
    method: str,
    lower: float,
    upper: float,
    iqr_multiplier: float,
    mad_threshold: float,
    z_threshold: float,
) -> Tuple[Optional[float], Optional[float]]:
    if method in {"winsor", "flag_only"}:
        return quantile_bounds(s, lower, upper)
    if method in {"iqr_cap", "drop_rows"}:
        return iqr_bounds(s, iqr_multiplier)
    if method == "mad_cap":
        return mad_bounds(s, mad_threshold)
    if method == "zscore_cap":
        return zscore_bounds(s, z_threshold)
    raise ValueError(f"Método não suportado: {method}")


def group_key_to_str(key: Any) -> str:
    if isinstance(key, tuple):
        return "||".join(str(x) for x in key)
    return str(key)


def compute_bounds(
    df_fit: pd.DataFrame,
    target_cols: List[str],
    group_cols: List[str],
    method: str,
    lower: float,
    upper: float,
    iqr_multiplier: float,
    mad_threshold: float,
    z_threshold: float,
    min_group_size: int,
) -> Dict[str, Any]:
    """Calcula limites globais e, opcionalmente, por grupo."""
    bounds: Dict[str, Any] = {"global": {}, "groups": {}, "group_cols": group_cols}
    for col in target_cols:
        lo, hi = compute_bounds_for_series(
            df_fit[col], method, lower, upper, iqr_multiplier, mad_threshold, z_threshold
        )
        bounds["global"][col] = {"lower": lo, "upper": hi}

    if group_cols:
        grouped = df_fit.groupby(group_cols, dropna=False, sort=False)
        for group_key, gdf in grouped:
            key_str = group_key_to_str(group_key)
            bounds["groups"][key_str] = {}
            for col in target_cols:
                valid_n = finite_series(gdf[col]).notna().sum()
                if valid_n < min_group_size:
                    bounds["groups"][key_str][col] = bounds["global"][col].copy()
                    bounds["groups"][key_str][col]["fallback_global"] = True
                else:
                    lo, hi = compute_bounds_for_series(
                        gdf[col], method, lower, upper, iqr_multiplier, mad_threshold, z_threshold
                    )
                    bounds["groups"][key_str][col] = {"lower": lo, "upper": hi, "fallback_global": False}
    return bounds


def load_bounds(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_bounds(path: Path, bounds: Dict[str, Any], metadata: Dict[str, Any]) -> None:
    payload = {"metadata": metadata, "bounds": bounds}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def bounds_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if "bounds" in payload and isinstance(payload["bounds"], dict):
        return payload["bounds"]
    return payload


def summarize_column(
    original: pd.Series,
    treated: pd.Series,
    col: str,
    method: str,
    strategy: str,
    group: Optional[str],
    lower_bound: Optional[float],
    upper_bound: Optional[float],
) -> ColumnReport:
    orig = finite_series(original)
    tr = finite_series(treated)
    valid = orig.notna()
    lo = -np.inf if lower_bound is None else lower_bound
    hi = np.inf if upper_bound is None else upper_bound
    below = valid & (orig < lo)
    above = valid & (orig > hi)
    n_below = int(below.sum())
    n_above = int(above.sum())
    n_valid = int(valid.sum())

    return ColumnReport(
        column=col,
        method=method,
        strategy=strategy,
        group=group,
        lower_bound=safe_float(lower_bound),
        upper_bound=safe_float(upper_bound),
        n_obs=n_valid,
        n_missing=int(orig.isna().sum()),
        n_below=n_below,
        n_above=n_above,
        n_capped_total=n_below + n_above,
        pct_capped_total=safe_float((n_below + n_above) / n_valid) if n_valid else 0.0,
        mean_before=safe_float(orig.mean()),
        std_before=safe_float(orig.std()),
        min_before=safe_float(orig.min()),
        p01_before=safe_float(orig.quantile(0.01)) if n_valid else None,
        median_before=safe_float(orig.median()),
        p99_before=safe_float(orig.quantile(0.99)) if n_valid else None,
        max_before=safe_float(orig.max()),
        mean_after=safe_float(tr.mean()),
        std_after=safe_float(tr.std()),
        min_after=safe_float(tr.min()),
        max_after=safe_float(tr.max()),
    )


def apply_global_treatment(
    df: pd.DataFrame,
    target_cols: List[str],
    bounds: Dict[str, Any],
    method: str,
    strategy: str,
    create_flags: bool,
    flag_prefix: str,
    keep_original_cols: bool,
) -> Tuple[pd.DataFrame, List[ColumnReport], pd.Series]:
    out = df.copy()
    reports: List[ColumnReport] = []
    row_outlier_count = pd.Series(0, index=out.index, dtype="int64")

    for col in target_cols:
        original = finite_series(out[col])
        lo = bounds["global"].get(col, {}).get("lower")
        hi = bounds["global"].get(col, {}).get("upper")
        lo_cmp = -np.inf if lo is None else lo
        hi_cmp = np.inf if hi is None else hi
        flag = original.notna() & ((original < lo_cmp) | (original > hi_cmp))
        row_outlier_count += flag.astype(int)

        if keep_original_cols:
            out[f"{col}__orig"] = out[col]
        if create_flags:
            out[f"{flag_prefix}{col}"] = flag.astype(int)

        if method in {"winsor", "iqr_cap", "mad_cap", "zscore_cap"}:
            out[col] = original.clip(lower=lo, upper=hi)
        elif method == "flag_only":
            out[col] = original
        elif method == "drop_rows":
            out[col] = original
        else:
            raise ValueError(f"Método não suportado: {method}")

        reports.append(summarize_column(original, out[col], col, method, strategy, None, lo, hi))

    return out, reports, row_outlier_count


def apply_group_treatment(
    df: pd.DataFrame,
    target_cols: List[str],
    bounds: Dict[str, Any],
    group_cols: List[str],
    method: str,
    strategy: str,
    create_flags: bool,
    flag_prefix: str,
    keep_original_cols: bool,
) -> Tuple[pd.DataFrame, List[ColumnReport], pd.Series]:
    out = df.copy()
    reports: List[ColumnReport] = []
    row_outlier_count = pd.Series(0, index=out.index, dtype="int64")

    for col in target_cols:
        if keep_original_cols:
            out[f"{col}__orig"] = out[col]
        if create_flags:
            out[f"{flag_prefix}{col}"] = 0

    grouped = out.groupby(group_cols, dropna=False, sort=False)
    for group_key, idx in grouped.groups.items():
        key_str = group_key_to_str(group_key)
        group_bounds = bounds.get("groups", {}).get(key_str, {})
        for col in target_cols:
            original = finite_series(out.loc[idx, col])
            col_bounds = group_bounds.get(col, bounds["global"].get(col, {}))
            lo = col_bounds.get("lower")
            hi = col_bounds.get("upper")
            lo_cmp = -np.inf if lo is None else lo
            hi_cmp = np.inf if hi is None else hi
            flag = original.notna() & ((original < lo_cmp) | (original > hi_cmp))
            row_outlier_count.loc[idx] += flag.astype(int)
            if create_flags:
                out.loc[idx, f"{flag_prefix}{col}"] = flag.astype(int)
            if method in {"winsor", "iqr_cap", "mad_cap", "zscore_cap"}:
                out.loc[idx, col] = original.clip(lower=lo, upper=hi)
            elif method in {"flag_only", "drop_rows"}:
                out.loc[idx, col] = original
            else:
                raise ValueError(f"Método não suportado: {method}")

            reports.append(
                summarize_column(
                    original,
                    out.loc[idx, col],
                    col,
                    method,
                    strategy,
                    key_str,
                    lo,
                    hi,
                )
            )

    return out, reports, row_outlier_count


def write_output(
    df_out: pd.DataFrame,
    report_df: pd.DataFrame,
    config_df: pd.DataFrame,
    path: Path,
    decimal_comma_csv: bool = False,
) -> None:
    suffix = path.suffix.lower()
    if suffix in [".xlsx", ".xlsm", ".xls"]:
        with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
            df_out.to_excel(writer, sheet_name="base_tratada", index=False)
            report_df.to_excel(writer, sheet_name="relatorio_outliers", index=False)
            config_df.to_excel(writer, sheet_name="config", index=False)

            workbook = writer.book
            fmt_header = workbook.add_format({"bold": True, "text_wrap": True, "valign": "top", "border": 1})
            fmt_pct = workbook.add_format({"num_format": "0.00%"})
            fmt_num = workbook.add_format({"num_format": "#,##0.000000"})

            for sheet_name, data in [
                ("base_tratada", df_out),
                ("relatorio_outliers", report_df),
                ("config", config_df),
            ]:
                ws = writer.sheets[sheet_name]
                ws.freeze_panes(1, 0)
                for col_num, value in enumerate(data.columns.values):
                    ws.write(0, col_num, value, fmt_header)
                    width = min(max(len(str(value)) + 2, 12), 36)
                    ws.set_column(col_num, col_num, width)
                if sheet_name == "relatorio_outliers" and "pct_capped_total" in data.columns:
                    pct_col = data.columns.get_loc("pct_capped_total")
                    ws.set_column(pct_col, pct_col, 16, fmt_pct)
                if sheet_name == "relatorio_outliers":
                    for c in ["lower_bound", "upper_bound", "mean_before", "std_before", "min_before", "p01_before", "median_before", "p99_before", "max_before", "mean_after", "std_after", "min_after", "max_after"]:
                        if c in data.columns:
                            col_i = data.columns.get_loc(c)
                            ws.set_column(col_i, col_i, 16, fmt_num)
    elif suffix == ".csv":
        if decimal_comma_csv:
            df_out.to_csv(path, index=False, sep=";", decimal=",")
        else:
            df_out.to_csv(path, index=False)
    elif suffix == ".parquet":
        df_out.to_parquet(path, index=False)
    else:
        raise ValueError(f"Formato de saída não suportado: {suffix}")


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {input_path}")

    output_path = Path(args.output) if args.output else input_path.with_name(f"{input_path.stem}_winsorizada.xlsx")
    report_csv_path = Path(args.report_csv) if args.report_csv else None

    df = read_input(input_path, args.sheet)
    original_rows = len(df)

    group_cols = split_cols(args.group_cols)
    include_cols = split_cols(args.include_cols)
    force_cols = split_cols(args.force_cols)
    exclude_cols = split_cols(args.exclude_cols)
    missing_groups = [c for c in group_cols if c not in df.columns]
    if missing_groups:
        raise ValueError(f"Colunas de grupo não existem na base: {missing_groups}")

    target_cols, diagnostics = infer_target_columns(
        df=df,
        strategy=args.strategy,
        include_cols=include_cols,
        force_cols=force_cols,
        exclude_cols=exclude_cols,
        treat_macro_vars=args.treat_macro_vars,
        treat_market_vars=args.treat_market_vars,
    )

    if not target_cols:
        raise ValueError(
            "Nenhuma coluna elegível para tratamento. Use --include-cols ou --force-cols para especificar colunas."
        )

    if args.drop_na_all_targets:
        df = df.dropna(how="all", subset=target_cols).copy()

    if args.fit_query:
        try:
            df_fit = df.query(args.fit_query).copy()
        except Exception as exc:
            raise ValueError(f"Erro ao aplicar --fit-query: {args.fit_query}. Detalhe: {exc}") from exc
        if df_fit.empty:
            raise ValueError("--fit-query retornou zero linhas; não é possível calcular limites.")
    else:
        df_fit = df.copy()

    if args.bounds_json_in:
        payload = load_bounds(Path(args.bounds_json_in))
        bounds = bounds_from_payload(payload)
    else:
        bounds = compute_bounds(
            df_fit=df_fit,
            target_cols=target_cols,
            group_cols=group_cols,
            method=args.method,
            lower=args.lower,
            upper=args.upper,
            iqr_multiplier=args.iqr_multiplier,
            mad_threshold=args.mad_threshold,
            z_threshold=args.z_threshold,
            min_group_size=args.min_group_size,
        )

    create_flags = not args.no_flags
    if group_cols:
        df_out, reports, row_outlier_count = apply_group_treatment(
            df=df,
            target_cols=target_cols,
            bounds=bounds,
            group_cols=group_cols,
            method=args.method,
            strategy=args.strategy,
            create_flags=create_flags,
            flag_prefix=args.flag_prefix,
            keep_original_cols=args.keep_original_cols,
        )
    else:
        df_out, reports, row_outlier_count = apply_global_treatment(
            df=df,
            target_cols=target_cols,
            bounds=bounds,
            method=args.method,
            strategy=args.strategy,
            create_flags=create_flags,
            flag_prefix=args.flag_prefix,
            keep_original_cols=args.keep_original_cols,
        )

    df_out["outlier_count_tratamento"] = row_outlier_count.astype(int)
    df_out["has_outlier_tratamento"] = (row_outlier_count > 0).astype(int)

    if args.method == "drop_rows":
        keep_mask = row_outlier_count == 0
        df_out = df_out.loc[keep_mask].copy()

    report_df = pd.DataFrame([asdict(r) for r in reports])
    # Para tratamento por grupo, também gera resumo agregado por coluna.
    if group_cols and not report_df.empty:
        agg = (
            report_df.groupby(["column", "method", "strategy"], as_index=False)
            .agg(
                group=("group", lambda x: "__AGREGADO__"),
                lower_bound=("lower_bound", "min"),
                upper_bound=("upper_bound", "max"),
                n_obs=("n_obs", "sum"),
                n_missing=("n_missing", "sum"),
                n_below=("n_below", "sum"),
                n_above=("n_above", "sum"),
                n_capped_total=("n_capped_total", "sum"),
                mean_before=("mean_before", "mean"),
                std_before=("std_before", "mean"),
                min_before=("min_before", "min"),
                p01_before=("p01_before", "mean"),
                median_before=("median_before", "mean"),
                p99_before=("p99_before", "mean"),
                max_before=("max_before", "max"),
                mean_after=("mean_after", "mean"),
                std_after=("std_after", "mean"),
                min_after=("min_after", "min"),
                max_after=("max_after", "max"),
            )
        )
        agg["pct_capped_total"] = np.where(agg["n_obs"] > 0, agg["n_capped_total"] / agg["n_obs"], 0)
        # Reordena colunas para casar com report_df.
        agg = agg[report_df.columns]
        report_df = pd.concat([agg, report_df], ignore_index=True)

    config = {
        "input": str(input_path),
        "sheet": args.sheet,
        "output": str(output_path),
        "original_rows": original_rows,
        "rows_after_optional_drop": len(df_out),
        "fit_rows_for_bounds": len(df_fit),
        "strategy": args.strategy,
        "method": args.method,
        "lower": args.lower,
        "upper": args.upper,
        "iqr_multiplier": args.iqr_multiplier,
        "mad_threshold": args.mad_threshold,
        "z_threshold": args.z_threshold,
        "group_cols": group_cols,
        "min_group_size": args.min_group_size,
        "fit_query": args.fit_query,
        "target_cols": target_cols,
        "diagnostics": diagnostics,
    }
    config_df = pd.DataFrame(
        [(k, json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v) for k, v in config.items()],
        columns=["parametro", "valor"],
    )

    print("\n=== Seleção de colunas para tratamento ===")
    print(f"Linhas na base original: {original_rows}")
    print(f"Linhas usadas para calcular limites: {len(df_fit)}")
    print(f"Método: {args.method} | Estratégia: {args.strategy}")
    print(f"Colunas tratadas ({len(target_cols)}): {', '.join(target_cols)}")
    print("\nResumo de caps por coluna:")
    display_cols = ["column", "group", "n_obs", "n_capped_total", "pct_capped_total", "lower_bound", "upper_bound"]
    print(report_df[display_cols].head(40).to_string(index=False))
    if len(report_df) > 40:
        print(f"... relatório completo contém {len(report_df)} linhas.")

    if args.bounds_json_out and not args.bounds_json_in:
        save_bounds(Path(args.bounds_json_out), bounds, metadata=config)
        print(f"\nLimites salvos em: {args.bounds_json_out}")

    if report_csv_path:
        if args.decimal_comma_csv:
            report_df.to_csv(report_csv_path, index=False, sep=";", decimal=",")
        else:
            report_df.to_csv(report_csv_path, index=False)
        print(f"Relatório CSV salvo em: {report_csv_path}")

    if args.dry_run:
        print("\nDry-run ativado: nenhum arquivo de base tratada foi salvo.")
        return 0

    write_output(
        df_out=df_out,
        report_df=report_df,
        config_df=config_df,
        path=output_path,
        decimal_comma_csv=args.decimal_comma_csv,
    )
    print(f"\nBase tratada salva em: {output_path}")
    print("Aba principal: base_tratada | Relatório: relatorio_outliers | Configuração: config")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        raise SystemExit(1)
