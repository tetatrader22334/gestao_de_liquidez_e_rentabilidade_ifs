#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análise descritiva e seleção de variáveis para regressão linear.

Uso típico:
    python 13_analise_descritiva_selecao_variaveis.py --input bases/base_final.xlsx --sheet base --target ROA --output-dir outputs/selecao_de_vars/geral --exclude-cols "ROE,NIM,flag_outlier__lcr_dec,flag_outlier__nsfr_dec"
O script gera:
    1. relatorio_analise_variaveis.xlsx
    2. relatorio_analise_variaveis.md
    3. variaveis_selecionadas.csv
    4. metadados_analise.json

Observação metodológica:
    A seleção automática é exploratória. Para dissertação, a especificação final da
    regressão deve combinar evidência estatística, teoria econômica e literatura sobre
    rentabilidade/liquidez bancária, evitando a escolha puramente data-driven.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import warnings
import unicodedata
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
import pandas as pd

try:
    from sklearn.feature_selection import f_regression
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LassoCV
    from sklearn.model_selection import KFold, TimeSeriesSplit
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except Exception:  # pragma: no cover - ambiente sem sklearn
    SKLEARN_AVAILABLE = False


# -----------------------------------------------------------------------------
# Configurações padrão
# -----------------------------------------------------------------------------

DEFAULT_ID_COLS = ["id_entidade"]
DEFAULT_TIME_COLS = ["AnoMes_ord"]
DEFAULT_EXCLUDE_REGEX = [
    r"^id$", r"id_entidade", r"ticker", r"cnpj", r"nome", r"instituicao",
]

TARGET_CANDIDATES = [
    "roa", "roa_dec", "roa_calc", "return_on_assets", "rentabilidade_ativos",
    "roe", "roe_dec", "return_on_equity", "rentabilidade_pl",
    "margem_liquida", "lucro_liquido_sobre_ativo",
]

MISSING_STRINGS = {
    "", " ", "na", "n/a", "nan", "null", "none", "-", "--", "#n/a", "#valor!",
}


@dataclass
class SelectionConfig:
    input_path: str
    sheet: Optional[str]
    target: str
    output_dir: str
    missing_threshold: float
    corr_threshold: float
    vif_threshold: float
    top_k: int
    min_abs_target_corr: float
    include_time_vars: bool
    include_entity_dummies: bool
    random_state: int


# -----------------------------------------------------------------------------
# Funções utilitárias
# -----------------------------------------------------------------------------

def normalize_name(name: str) -> str:
    """Normaliza nomes de colunas para comparação sem alterar o DataFrame original."""
    text = str(name).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def ensure_output_dir(path: str | Path) -> Path:
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    return out


def coerce_numeric_series(s: pd.Series) -> pd.Series:
    """Converte valores numéricos preservando NaN; útil para colunas object importadas do Excel."""
    if pd.api.types.is_numeric_dtype(s):
        return s
    cleaned = s.astype(str).str.strip()
    cleaned = cleaned.mask(cleaned.str.lower().isin(MISSING_STRINGS), np.nan)
    # Trata formato brasileiro quando houver vírgula decimal e ponto de milhar.
    comma_decimal = cleaned.str.contains(r",", regex=True, na=False).mean() > 0.2
    if comma_decimal:
        cleaned = cleaned.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(cleaned, errors="coerce")


def load_base(input_path: str, sheet: Optional[str]) -> pd.DataFrame:
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    suffix = path.suffix.lower()
    if suffix in [".xlsx", ".xls", ".xlsm"]:
        df = pd.read_excel(path, sheet_name=sheet or 0)
    elif suffix in [".csv", ".txt"]:
        df = pd.read_csv(path)
    elif suffix in [".parquet"]:
        df = pd.read_parquet(path)
    else:
        raise ValueError("Formato não suportado. Use .xlsx, .xls, .csv ou .parquet.")

    df.columns = [str(c).strip() for c in df.columns]
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].replace(list(MISSING_STRINGS), np.nan)
            converted = coerce_numeric_series(df[col])
            # Aceita conversão quando gera proporção relevante de números.
            if pd.api.types.is_numeric_dtype(converted):
                numeric_ratio = converted.notna().mean()
                original_non_missing = df[col].notna().mean()
                if original_non_missing == 0 or numeric_ratio >= 0.75 * original_non_missing:
                    df[col] = converted
    return df


def find_col(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    norm_to_original = {normalize_name(c): c for c in df.columns}
    for cand in candidates:
        c_norm = normalize_name(cand)
        if c_norm in norm_to_original:
            return norm_to_original[c_norm]
    return None


def add_derived_targets(df: pd.DataFrame) -> list[str]:
    """Cria alvos usuais de rentabilidade quando há colunas suficientes."""
    created: list[str] = []
    net_income_col = find_col(df, [
        "is_netIncomeFromContinuingOps", "is_net_income", "lucro_liquido",
        "resultado_liquido", "net_income",
    ])
    assets_col = find_col(df, [
        "bs_totalAssets", "bs_total_assets", "ativos_totais_banco_brl", "ativo_total",
        "total_assets",
    ])
    if net_income_col and assets_col and "ROA_calc" not in df.columns:
        denom = pd.to_numeric(df[assets_col], errors="coerce").replace(0, np.nan)
        df["ROA_calc"] = pd.to_numeric(df[net_income_col], errors="coerce") / denom
        created.append("ROA_calc")
    return created


def resolve_target(df: pd.DataFrame, requested_target: str) -> tuple[str, list[str]]:
    created = add_derived_targets(df)
    if requested_target and requested_target.lower() != "auto":
        target_col = find_col(df, [requested_target])
        if not target_col:
            raise ValueError(
                f"Variável-alvo '{requested_target}' não encontrada. "
                f"Colunas disponíveis: {', '.join(df.columns[:30])}..."
            )
        return target_col, created

    target_col = find_col(df, TARGET_CANDIDATES)
    if target_col:
        return target_col, created

    raise ValueError(
        "Não foi possível detectar automaticamente a variável-alvo. "
        "Informe com --target NOME_DA_COLUNA."
    )


def safe_divide(a: float, b: float) -> float:
    if b in [0, 0.0] or pd.isna(b):
        return np.nan
    return a / b


# -----------------------------------------------------------------------------
# Estatísticas descritivas
# -----------------------------------------------------------------------------

def descriptive_numeric(df: pd.DataFrame) -> pd.DataFrame:
    numeric = df.select_dtypes(include=[np.number]).copy()
    rows = []
    n_total = len(df)
    for col in numeric.columns:
        s = pd.to_numeric(numeric[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
        valid = s.dropna()
        mean = valid.mean() if len(valid) else np.nan
        std = valid.std(ddof=1) if len(valid) > 1 else np.nan
        rows.append({
            "variavel": col,
            "n": int(valid.shape[0]),
            "missing": int(s.isna().sum()),
            "missing_pct": safe_divide(s.isna().sum(), n_total),
            "media": mean,
            "moda": valid.mode().iloc[0] if len(valid.mode()) else np.nan,
            "mediana": valid.median() if len(valid) else np.nan,
            "desvio_padrao": std,
            "coef_variacao": safe_divide(std, abs(mean)) if pd.notna(mean) else np.nan,
            "min": valid.min() if len(valid) else np.nan,
            "q1": valid.quantile(0.25) if len(valid) else np.nan,
            "q3": valid.quantile(0.75) if len(valid) else np.nan,
            "max": valid.max() if len(valid) else np.nan,
            "assimetria": valid.skew() if len(valid) > 2 else np.nan,
            "curtose": valid.kurt() if len(valid) > 3 else np.nan,
            "zeros": int((valid == 0).sum()) if len(valid) else 0,
            "zeros_pct_validos": safe_divide((valid == 0).sum(), len(valid)) if len(valid) else np.nan,
            "valores_unicos": int(valid.nunique(dropna=True)),
        })
    return pd.DataFrame(rows).sort_values(["missing_pct", "variavel"]).reset_index(drop=True)


def descriptive_categorical(df: pd.DataFrame) -> pd.DataFrame:
    cats = df.select_dtypes(exclude=[np.number]).copy()
    rows = []
    n_total = len(df)
    for col in cats.columns:
        s = cats[col]
        mode = s.mode(dropna=True)
        top = mode.iloc[0] if len(mode) else np.nan
        top_freq = int((s == top).sum()) if pd.notna(top) else 0
        rows.append({
            "variavel": col,
            "n": int(s.notna().sum()),
            "missing": int(s.isna().sum()),
            "missing_pct": safe_divide(s.isna().sum(), n_total),
            "valores_unicos": int(s.nunique(dropna=True)),
            "moda": top,
            "freq_moda": top_freq,
            "freq_moda_pct": safe_divide(top_freq, s.notna().sum()),
        })
    return pd.DataFrame(rows).sort_values(["missing_pct", "variavel"]).reset_index(drop=True)


def quality_checks(df: pd.DataFrame, id_cols: list[str], time_cols: list[str]) -> dict[str, pd.DataFrame]:
    numeric = df.select_dtypes(include=[np.number]).replace([np.inf, -np.inf], np.nan)
    n = len(df)
    missing = pd.DataFrame({
        "variavel": df.columns,
        "missing": [df[c].isna().sum() for c in df.columns],
        "missing_pct": [df[c].isna().mean() for c in df.columns],
        "dtype": [str(df[c].dtype) for c in df.columns],
        "valores_unicos": [df[c].nunique(dropna=True) for c in df.columns],
    }).sort_values("missing_pct", ascending=False)

    low_info = missing[(missing["missing_pct"] >= 0.80) | (missing["valores_unicos"] <= 1)].copy()

    duplicates_total = pd.DataFrame([{
        "metric": "linhas_duplicadas_completas",
        "valor": int(df.duplicated().sum()),
        "pct": safe_divide(df.duplicated().sum(), n),
    }])

    key_cols = [c for c in id_cols + time_cols if c in df.columns]
    if key_cols:
        dup_key = df[df.duplicated(subset=key_cols, keep=False)][key_cols].copy()
        duplicates_key = (
            dup_key.value_counts(key_cols).reset_index(name="n_ocorrencias")
            if not dup_key.empty else pd.DataFrame(columns=key_cols + ["n_ocorrencias"])
        )
    else:
        duplicates_key = pd.DataFrame(columns=["aviso"])
        duplicates_key.loc[0, "aviso"] = "Nenhuma chave id/tempo encontrada para teste de duplicidade."

    # Possíveis problemas para logs: variáveis com valores <= 0.
    log_issues_rows = []
    for col in numeric.columns:
        s = numeric[col].dropna()
        if len(s) == 0:
            continue
        n_non_pos = int((s <= 0).sum())
        if n_non_pos > 0:
            log_issues_rows.append({
                "variavel": col,
                "valores_menores_ou_iguais_a_zero": n_non_pos,
                "pct_validos": safe_divide(n_non_pos, len(s)),
                "min": s.min(),
            })
    log_issues = pd.DataFrame(log_issues_rows).sort_values("pct_validos", ascending=False)

    return {
        "missing_por_variavel": missing,
        "baixa_informacao": low_info,
        "duplicidades_gerais": duplicates_total,
        "duplicidades_chave": duplicates_key,
        "problemas_para_log": log_issues,
    }


# -----------------------------------------------------------------------------
# Seleção de variáveis
# -----------------------------------------------------------------------------

def build_candidate_matrix(
    df: pd.DataFrame,
    target_col: str,
    include_time_vars: bool,
    include_entity_dummies: bool,
    exclude_cols: Optional[list[str]] = None,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    exclude_cols = exclude_cols or []
    excluded_reasons = []

    y = pd.to_numeric(df[target_col], errors="coerce").replace([np.inf, -np.inf], np.nan)

    # Entidade como dummy é opcional, pois pode capturar efeitos fixos institucionais.
    work = df.copy()
    if include_entity_dummies and "id_entidade" in work.columns:
        dummies = pd.get_dummies(work["id_entidade"], prefix="fe_entidade", drop_first=True, dtype=float)
        work = pd.concat([work, dummies], axis=1)

    numeric_cols = work.select_dtypes(include=[np.number]).columns.tolist()
    candidates = []
    normalized_target = normalize_name(target_col)

    for col in numeric_cols:
        norm = normalize_name(col)
        reason = None
        if col == target_col or norm == normalized_target:
            reason = "variavel_alvo"
        elif col in exclude_cols:
            reason = "excluida_usuario"
        elif any(re.search(pattern, norm) for pattern in DEFAULT_EXCLUDE_REGEX):
            reason = "identificador"
        elif not include_time_vars and norm in [normalize_name(c) for c in DEFAULT_TIME_COLS + ["trimestre", "ano", "mes"]]:
            reason = "tempo_excluido_por_padrao"
        elif "target" in norm or "roa" in norm and norm != normalized_target:
            # Evita vazamento quando houver outras versões da rentabilidade.
            reason = "possivel_vazamento_alvo"
        elif norm.startswith("fe_entidade") and not include_entity_dummies:
            reason = "dummy_entidade_desabilitada"

        if reason:
            excluded_reasons.append({"variavel": col, "motivo": reason})
        else:
            candidates.append(col)

    X = work[candidates].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    excluded = pd.DataFrame(excluded_reasons)
    return X, y, excluded


def target_correlations(X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
    rows = []
    mask_y = y.notna()
    for col in X.columns:
        xy = pd.concat([X[col], y], axis=1).dropna()
        if xy.shape[0] < 3 or xy[col].nunique() <= 1:
            corr = np.nan
        else:
            corr = xy.iloc[:, 0].corr(xy.iloc[:, 1])
        rows.append({
            "variavel": col,
            "corr_com_alvo": corr,
            "abs_corr_com_alvo": abs(corr) if pd.notna(corr) else np.nan,
            "n_corr": int(xy.shape[0]),
        })
    return pd.DataFrame(rows).sort_values("abs_corr_com_alvo", ascending=False).reset_index(drop=True)


def filter_candidates(
    X: pd.DataFrame,
    y: pd.Series,
    missing_threshold: float,
    min_abs_target_corr: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    report_rows = []
    keep_cols = []
    corr_df = target_correlations(X, y).set_index("variavel")

    for col in X.columns:
        s = X[col]
        miss = s.isna().mean()
        nunique = s.nunique(dropna=True)
        variance = s.var(skipna=True)
        corr = corr_df.loc[col, "corr_com_alvo"] if col in corr_df.index else np.nan
        abs_corr = abs(corr) if pd.notna(corr) else np.nan
        status = "mantida"
        motivo = "aprovada_filtros_basicos"

        if miss > missing_threshold:
            status, motivo = "removida", f"missing_pct>{missing_threshold:.2f}"
        elif nunique <= 1:
            status, motivo = "removida", "constante_ou_quase_constante"
        elif pd.isna(variance) or variance <= 0:
            status, motivo = "removida", "variancia_zero"
        elif min_abs_target_corr > 0 and (pd.isna(abs_corr) or abs_corr < min_abs_target_corr):
            status, motivo = "removida", f"abs_corr_alvo<{min_abs_target_corr:.3f}"
        else:
            keep_cols.append(col)

        report_rows.append({
            "variavel": col,
            "status_filtro_basico": status,
            "motivo": motivo,
            "missing_pct": miss,
            "valores_unicos": nunique,
            "variancia": variance,
            "corr_com_alvo": corr,
            "abs_corr_com_alvo": abs_corr,
        })

    return X[keep_cols].copy(), pd.DataFrame(report_rows).sort_values(["status_filtro_basico", "abs_corr_com_alvo"], ascending=[True, False])


def prune_pairwise_correlation(
    X: pd.DataFrame,
    y: pd.Series,
    threshold: float,
) -> tuple[list[str], pd.DataFrame]:
    if X.shape[1] <= 1:
        return X.columns.tolist(), pd.DataFrame()

    corr_target = target_correlations(X, y).set_index("variavel")["abs_corr_com_alvo"].fillna(0)
    corr = X.corr(numeric_only=True).abs()
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))

    dropped = set()
    rows = []
    pairs = []
    for col in upper.columns:
        high = upper.index[upper[col] > threshold].tolist()
        for row in high:
            pairs.append((row, col, upper.loc[row, col]))

    # Remove primeiro as relações mais extremas.
    pairs = sorted(pairs, key=lambda t: t[2], reverse=True)
    for a, b, c in pairs:
        if a in dropped or b in dropped:
            continue
        score_a = corr_target.get(a, 0)
        score_b = corr_target.get(b, 0)
        drop = a if score_a < score_b else b
        keep = b if drop == a else a
        dropped.add(drop)
        rows.append({
            "variavel_removida": drop,
            "variavel_mantida": keep,
            "corr_entre_variaveis": c,
            "abs_corr_alvo_removida": score_a if drop == a else score_b,
            "abs_corr_alvo_mantida": score_b if keep == b else score_a,
            "motivo": f"correlacao_preditiva_acima_de_{threshold:.2f}",
        })

    keep_cols = [c for c in X.columns if c not in dropped]
    return keep_cols, pd.DataFrame(rows)


def select_with_lasso_and_f_test(
    X: pd.DataFrame,
    y: pd.Series,
    top_k: int,
    random_state: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not SKLEARN_AVAILABLE:
        msg = pd.DataFrame([{
            "metodo": "sklearn",
            "aviso": "scikit-learn não está instalado; LassoCV e f_regression foram ignorados.",
        }])
        return pd.DataFrame(), msg

    data = pd.concat([X, y.rename("__target__")], axis=1).dropna(subset=["__target__"])
    X2 = data[X.columns]
    y2 = data["__target__"]

    if X2.shape[0] < 10 or X2.shape[1] == 0:
        msg = pd.DataFrame([{
            "metodo": "selecao",
            "aviso": "Amostra insuficiente ou nenhuma variável candidata após filtros básicos.",
        }])
        return pd.DataFrame(), msg

    # Remove colunas totalmente vazias depois do recorte de y.
    X2 = X2.loc[:, X2.notna().any(axis=0)]
    if X2.shape[1] == 0:
        return pd.DataFrame(), pd.DataFrame([{"metodo": "selecao", "aviso": "Todas as candidatas ficaram vazias."}])

    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()
    X_imp = imputer.fit_transform(X2)
    X_scaled = scaler.fit_transform(X_imp)

    # f_regression: ranking univariado linear.
    try:
        f_scores, p_values = f_regression(X_scaled, y2.values)
    except Exception:
        f_scores = np.repeat(np.nan, X2.shape[1])
        p_values = np.repeat(np.nan, X2.shape[1])

    # LassoCV: seleção multivariada com regularização L1.
    n = X2.shape[0]
    if "AnoMes_ord" in data.columns and data["AnoMes_ord"].nunique() >= 5:
        cv = TimeSeriesSplit(n_splits=min(5, max(2, n // 30)))
    else:
        cv = KFold(n_splits=min(5, max(2, min(n, 5))), shuffle=True, random_state=random_state)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            lasso = LassoCV(cv=cv, random_state=random_state, max_iter=50000, n_alphas=100)
            lasso.fit(X_scaled, y2.values)
        coefs = lasso.coef_
        alpha = float(lasso.alpha_)
    except Exception:
        coefs = np.repeat(np.nan, X2.shape[1])
        alpha = np.nan

    ranking = pd.DataFrame({
        "variavel": X2.columns,
        "f_score": f_scores,
        "p_value_f_regression": p_values,
        "lasso_coef_padronizado": coefs,
        "abs_lasso_coef": np.abs(coefs),
        "lasso_alpha": alpha,
    })
    ranking["rank_f_score"] = ranking["f_score"].rank(ascending=False, method="min")
    ranking["rank_lasso"] = ranking["abs_lasso_coef"].rank(ascending=False, method="min")
    ranking["selecionada_f_test_top_k"] = ranking["rank_f_score"] <= min(top_k, len(ranking))
    ranking["selecionada_lasso"] = ranking["abs_lasso_coef"].fillna(0) > 1e-12
    ranking["selecionada_union"] = ranking["selecionada_f_test_top_k"] | ranking["selecionada_lasso"]
    ranking = ranking.sort_values(["selecionada_union", "abs_lasso_coef", "f_score"], ascending=[False, False, False])

    notes = pd.DataFrame([{
        "metodo": "LassoCV + f_regression",
        "observacoes": (
            "LassoCV usa regularização L1 e f_regression mede associação linear univariada. "
            "A união dos dois rankings é usada antes da poda por VIF."
        ),
        "n_obs_usadas": int(X2.shape[0]),
        "n_variaveis_avaliadas": int(X2.shape[1]),
        "lasso_alpha": alpha,
    }])
    return ranking, notes


def compute_vif_table(X: pd.DataFrame) -> pd.DataFrame:
    """Calcula VIF sem depender de statsmodels."""
    if X.shape[1] == 0:
        return pd.DataFrame(columns=["variavel", "vif"])
    if X.shape[1] == 1:
        return pd.DataFrame({"variavel": X.columns, "vif": [1.0]})

    X_clean = X.copy().replace([np.inf, -np.inf], np.nan)
    X_clean = X_clean.fillna(X_clean.median(numeric_only=True))
    X_arr = X_clean.to_numpy(dtype=float)

    # Padronização evita problemas de escala.
    std = X_arr.std(axis=0, ddof=0)
    std[std == 0] = np.nan
    X_arr = (X_arr - np.nanmean(X_arr, axis=0)) / std
    X_arr = np.nan_to_num(X_arr, nan=0.0, posinf=0.0, neginf=0.0)

    rows = []
    for j, col in enumerate(X.columns):
        yj = X_arr[:, j]
        others = np.delete(X_arr, j, axis=1)
        if others.shape[1] == 0:
            vif = 1.0
        else:
            others = np.column_stack([np.ones(others.shape[0]), others])
            try:
                beta, *_ = np.linalg.lstsq(others, yj, rcond=None)
                y_hat = others @ beta
                ss_res = np.sum((yj - y_hat) ** 2)
                ss_tot = np.sum((yj - yj.mean()) ** 2)
                r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
                if r2 >= 0.999999:
                    vif = np.inf
                else:
                    vif = 1 / (1 - r2)
            except Exception:
                vif = np.nan
        rows.append({"variavel": col, "vif": vif})
    return pd.DataFrame(rows).sort_values("vif", ascending=False).reset_index(drop=True)


def iterative_vif_pruning(
    X: pd.DataFrame,
    y: pd.Series,
    vif_threshold: float,
    max_iter: int = 200,
) -> tuple[list[str], pd.DataFrame, pd.DataFrame]:
    cols = X.columns.tolist()
    corr_target = target_correlations(X, y).set_index("variavel")["abs_corr_com_alvo"].fillna(0).to_dict()
    removed_rows = []

    for _ in range(max_iter):
        if len(cols) <= 1:
            break
        vif = compute_vif_table(X[cols])
        if vif.empty:
            break
        max_vif = vif.iloc[0]["vif"]
        if pd.isna(max_vif) or max_vif <= vif_threshold:
            break

        # Entre variáveis com VIF alto, remove a menos correlacionada com o alvo.
        high_vif = vif[vif["vif"] > vif_threshold].copy()
        high_vif["abs_corr_com_alvo"] = high_vif["variavel"].map(corr_target).fillna(0)
        high_vif = high_vif.sort_values(["abs_corr_com_alvo", "vif"], ascending=[True, False])
        drop = high_vif.iloc[0]["variavel"]
        removed_rows.append({
            "variavel_removida": drop,
            "vif_no_momento_remocao": float(high_vif.iloc[0]["vif"]),
            "abs_corr_com_alvo": float(high_vif.iloc[0]["abs_corr_com_alvo"]),
            "motivo": f"VIF>{vif_threshold:.2f}",
        })
        cols.remove(drop)

    final_vif = compute_vif_table(X[cols]) if cols else pd.DataFrame(columns=["variavel", "vif"])
    return cols, pd.DataFrame(removed_rows), final_vif


def run_variable_selection(
    df: pd.DataFrame,
    target_col: str,
    cfg: SelectionConfig,
    exclude_cols: Optional[list[str]] = None,
) -> dict[str, pd.DataFrame | list[str]]:
    X_raw, y, excluded_initial = build_candidate_matrix(
        df=df,
        target_col=target_col,
        include_time_vars=cfg.include_time_vars,
        include_entity_dummies=cfg.include_entity_dummies,
        exclude_cols=exclude_cols,
    )

    y_desc = pd.DataFrame([{
        "target": target_col,
        "n": int(y.notna().sum()),
        "missing": int(y.isna().sum()),
        "missing_pct": y.isna().mean(),
        "media": y.mean(skipna=True),
        "mediana": y.median(skipna=True),
        "desvio_padrao": y.std(skipna=True),
        "min": y.min(skipna=True),
        "max": y.max(skipna=True),
    }])

    X_basic, basic_filter_report = filter_candidates(
        X_raw, y, missing_threshold=cfg.missing_threshold,
        min_abs_target_corr=cfg.min_abs_target_corr,
    )

    kept_corr_cols, pairwise_corr_removed = prune_pairwise_correlation(
        X_basic, y, threshold=cfg.corr_threshold,
    )
    X_corr = X_basic[kept_corr_cols].copy()

    ranking, selection_notes = select_with_lasso_and_f_test(
        X_corr, y, top_k=cfg.top_k, random_state=cfg.random_state,
    )

    if ranking.empty:
        pre_vif_cols = target_correlations(X_corr, y).head(cfg.top_k)["variavel"].tolist()
    else:
        pre_vif_cols = ranking.loc[ranking["selecionada_union"], "variavel"].tolist()
        if len(pre_vif_cols) == 0:
            pre_vif_cols = ranking.head(cfg.top_k)["variavel"].tolist()

    X_pre_vif = X_corr[pre_vif_cols].copy() if pre_vif_cols else pd.DataFrame(index=df.index)
    final_cols, vif_removed, final_vif = iterative_vif_pruning(
        X_pre_vif, y, vif_threshold=cfg.vif_threshold,
    )

    target_corr_all = target_correlations(X_raw, y)
    selected_final = pd.DataFrame({"variavel": final_cols})
    if not selected_final.empty:
        selected_final = selected_final.merge(
            target_corr_all[["variavel", "corr_com_alvo", "abs_corr_com_alvo"]],
            on="variavel", how="left"
        ).merge(final_vif, on="variavel", how="left")
        if not ranking.empty:
            selected_final = selected_final.merge(
                ranking[["variavel", "f_score", "p_value_f_regression", "lasso_coef_padronizado", "abs_lasso_coef"]],
                on="variavel", how="left"
            )
        selected_final = selected_final.sort_values(["abs_lasso_coef", "abs_corr_com_alvo"], ascending=False)

    return {
        "target_descritivo": y_desc,
        "excluidas_iniciais": excluded_initial,
        "filtros_basicos": basic_filter_report,
        "correlacao_com_alvo": target_corr_all,
        "removidas_correlacao_pares": pairwise_corr_removed,
        "ranking_modelos": ranking,
        "notas_selecao": selection_notes,
        "pre_vif": pd.DataFrame({"variavel": pre_vif_cols}),
        "removidas_vif": vif_removed,
        "vif_final": final_vif,
        "variaveis_selecionadas": selected_final,
        "final_cols": final_cols,
    }


# -----------------------------------------------------------------------------
# Relatórios
# -----------------------------------------------------------------------------

def write_excel_report(
    out_path: Path,
    sheets: dict[str, pd.DataFrame],
) -> None:
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        for name, df in sheets.items():
            safe_name = re.sub(r"[\\/*?:\[\]]", "_", name)[:31]
            if df is None:
                continue
            if isinstance(df, pd.Series):
                df = df.to_frame()
            if len(df) == 0:
                df = pd.DataFrame({"info": ["Sem registros para esta seção."]})
            df.to_excel(writer, sheet_name=safe_name, index=False)

            ws = writer.book[safe_name]
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for col_cells in ws.columns:
                max_len = 0
                col_letter = col_cells[0].column_letter
                for cell in col_cells[:1000]:
                    value = cell.value
                    if value is not None:
                        max_len = max(max_len, len(str(value)))
                ws.column_dimensions[col_letter].width = min(max(max_len + 2, 10), 45)


def markdown_table(df: pd.DataFrame, max_rows: int = 15) -> str:
    if df is None or df.empty:
        return "Sem registros."
    try:
        return df.head(max_rows).to_markdown(index=False)
    except Exception:
        return "```text\n" + df.head(max_rows).to_string(index=False) + "\n```"


def write_markdown_report(
    out_path: Path,
    cfg: SelectionConfig,
    df: pd.DataFrame,
    target_col: str,
    created_targets: list[str],
    numeric_desc: pd.DataFrame,
    categorical_desc: pd.DataFrame,
    quality: dict[str, pd.DataFrame],
    selection: dict[str, pd.DataFrame | list[str]],
) -> None:
    selected = selection["variaveis_selecionadas"]
    formula = ""
    if isinstance(selected, pd.DataFrame) and not selected.empty:
        rhs = " + ".join([f"Q('{v}')" for v in selected["variavel"].tolist()])
        formula = f"Q('{target_col}') ~ {rhs}"
    else:
        formula = "Nenhuma variável final selecionada. Revise os filtros ou informe outro alvo."

    text = f"""# Relatório de análise descritiva e seleção de variáveis

**Arquivo analisado:** `{cfg.input_path}`  
**Aba:** `{cfg.sheet or 'primeira aba'}`  
**Data de geração:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Variável-alvo:** `{target_col}`

## 1. Visão geral da base

- Número de linhas: **{df.shape[0]}**
- Número de colunas: **{df.shape[1]}**
- Variáveis numéricas: **{df.select_dtypes(include=[np.number]).shape[1]}**
- Variáveis categóricas/textuais: **{df.select_dtypes(exclude=[np.number]).shape[1]}**
- Alvos derivados criados automaticamente: **{', '.join(created_targets) if created_targets else 'nenhum'}**

## 2. Estatísticas descritivas numéricas — primeiras variáveis por menor missing

{markdown_table(numeric_desc, 20)}

## 3. Estatísticas descritivas categóricas

{markdown_table(categorical_desc, 20)}

## 4. Diagnóstico de qualidade da base

### 4.1 Variáveis com maior percentual de missing

{markdown_table(quality['missing_por_variavel'].sort_values('missing_pct', ascending=False), 20)}

### 4.2 Variáveis com baixa informação

{markdown_table(quality['baixa_informacao'], 20)}

### 4.3 Possíveis problemas para transformações logarítmicas

Estas variáveis têm valores menores ou iguais a zero. Caso sejam usadas em log, exigem tratamento prévio.

{markdown_table(quality['problemas_para_log'], 20)}

## 5. Seleção de variáveis para regressão linear

Parâmetros usados:

- Máximo de missing permitido nos preditores: **{cfg.missing_threshold:.2%}**
- Limiar de correlação entre preditores para poda: **{cfg.corr_threshold:.2f}**
- Limiar de VIF: **{cfg.vif_threshold:.2f}**
- Top-k do teste F univariado: **{cfg.top_k}**
- Correlação mínima absoluta com o alvo: **{cfg.min_abs_target_corr:.4f}**
- Variáveis temporais incluídas: **{cfg.include_time_vars}**
- Dummies de entidade incluídas: **{cfg.include_entity_dummies}**

### 5.1 Variáveis mais correlacionadas com o alvo

{markdown_table(selection['correlacao_com_alvo'], 25)}

### 5.2 Ranking por LassoCV e teste F

{markdown_table(selection['ranking_modelos'], 25)}

### 5.3 Variáveis removidas por multicolinearidade entre preditores

{markdown_table(selection['removidas_correlacao_pares'], 20)}

### 5.4 Variáveis removidas por VIF

{markdown_table(selection['removidas_vif'], 20)}

### 5.5 Variáveis finais sugeridas

{markdown_table(selected, 40) if isinstance(selected, pd.DataFrame) else 'Sem registros.'}

## 6. Fórmula sugerida para posterior regressão linear em `statsmodels`

```python
formula = "{formula}"
```

## 7. Interpretação metodológica

A seleção foi construída como etapa exploratória para reduzir dimensionalidade e problemas de multicolinearidade antes da regressão linear. O procedimento combina: filtros de qualidade dos dados, associação linear univariada com a variável-alvo, regularização L1 via LassoCV, poda de pares altamente correlacionados e poda iterativa por VIF. Em aplicações acadêmicas, recomenda-se que a especificação final seja validada por fundamentação teórica, coerência econômica, diagnóstico de resíduos e testes de robustez.

## 8. Referências metodológicas em formato ABNT

GUYON, Isabelle; ELISSEEFF, André. An introduction to variable and feature selection. *Journal of Machine Learning Research*, v. 3, p. 1157-1182, 2003.

TIBSHIRANI, Robert. Regression shrinkage and selection via the lasso. *Journal of the Royal Statistical Society: Series B*, v. 58, n. 1, p. 267-288, 1996.

O'BRIEN, Robert M. A caution regarding rules of thumb for variance inflation factors. *Quality & Quantity*, v. 41, p. 673-690, 2007.

JAMES, Gareth et al. *An introduction to statistical learning: with applications in R*. 2. ed. New York: Springer, 2021.
"""
    out_path.write_text(text, encoding="utf-8")


def write_metadata(out_path: Path, cfg: SelectionConfig, target_col: str, created_targets: list[str], outputs: dict[str, str]) -> None:
    metadata = {
        "config": asdict(cfg),
        "target_col": target_col,
        "created_targets": created_targets,
        "outputs": outputs,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sklearn_available": SKLEARN_AVAILABLE,
    }
    out_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Computa estatísticas descritivas, seleciona variáveis para regressão linear e gera relatório."
    )
    parser.add_argument("--input", required=True, help="Caminho da base (.xlsx, .csv ou .parquet).")
    parser.add_argument("--sheet", default=None, help="Nome da aba do Excel. Se omitido, usa a primeira aba.")
    parser.add_argument("--target", default="auto", help="Variável-alvo. Use 'auto' para detectar/criar ROA_calc.")
    parser.add_argument("--output-dir", default="resultados_analise", help="Pasta de saída.")
    parser.add_argument("--missing-threshold", type=float, default=0.40, help="Máximo de missing permitido por preditor.")
    parser.add_argument("--corr-threshold", type=float, default=0.95, help="Limiar de |correlação| para remover preditores redundantes.")
    parser.add_argument("--vif-threshold", type=float, default=10.0, help="Limiar de VIF para poda iterativa.")
    parser.add_argument("--top-k", type=int, default=25, help="Número de variáveis mantidas pelo ranking univariado.")
    parser.add_argument("--min-abs-target-corr", type=float, default=0.0, help="Correlação mínima absoluta com o alvo; 0 não filtra por correlação.")
    parser.add_argument("--include-time-vars", action="store_true", help="Inclui variáveis temporais numéricas como preditores.")
    parser.add_argument("--include-entity-dummies", action="store_true", help="Cria dummies de id_entidade para efeitos fixos exploratórios.")
    parser.add_argument("--exclude-cols", default="", help="Colunas extras a excluir, separadas por vírgula.")
    parser.add_argument("--random-state", type=int, default=42, help="Semente aleatória.")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    out_dir = ensure_output_dir(args.output_dir)

    cfg = SelectionConfig(
        input_path=args.input,
        sheet=args.sheet,
        target=args.target,
        output_dir=str(out_dir),
        missing_threshold=args.missing_threshold,
        corr_threshold=args.corr_threshold,
        vif_threshold=args.vif_threshold,
        top_k=args.top_k,
        min_abs_target_corr=args.min_abs_target_corr,
        include_time_vars=args.include_time_vars,
        include_entity_dummies=args.include_entity_dummies,
        random_state=args.random_state,
    )

    print(f"[INFO] Carregando base: {args.input}")
    df = load_base(args.input, args.sheet)
    target_col, created_targets = resolve_target(df, args.target)
    print(f"[INFO] Variável-alvo usada: {target_col}")
    if created_targets:
        print(f"[INFO] Alvos derivados criados: {created_targets}")

    id_cols = [c for c in DEFAULT_ID_COLS if c in df.columns]
    time_cols = [c for c in DEFAULT_TIME_COLS if c in df.columns]

    numeric_desc = descriptive_numeric(df)
    categorical_desc = descriptive_categorical(df)
    quality = quality_checks(df, id_cols=id_cols, time_cols=time_cols)

    exclude_cols = [c.strip() for c in args.exclude_cols.split(",") if c.strip()]
    selection = run_variable_selection(df, target_col, cfg, exclude_cols=exclude_cols)

    excel_path = out_dir / "relatorio_analise_variaveis.xlsx"
    md_path = out_dir / "relatorio_analise_variaveis.md"
    csv_path = out_dir / "variaveis_selecionadas.csv"
    metadata_path = out_dir / "metadados_analise.json"

    sheets = {
        "descritivas_numericas": numeric_desc,
        "descritivas_categoricas": categorical_desc,
        "missing_por_variavel": quality["missing_por_variavel"],
        "baixa_informacao": quality["baixa_informacao"],
        "duplicidades_gerais": quality["duplicidades_gerais"],
        "duplicidades_chave": quality["duplicidades_chave"],
        "problemas_para_log": quality["problemas_para_log"],
        "target_descritivo": selection["target_descritivo"],
        "excluidas_iniciais": selection["excluidas_iniciais"],
        "filtros_basicos": selection["filtros_basicos"],
        "corr_com_alvo": selection["correlacao_com_alvo"],
        "removidas_corr_pares": selection["removidas_correlacao_pares"],
        "ranking_modelos": selection["ranking_modelos"],
        "notas_selecao": selection["notas_selecao"],
        "pre_vif": selection["pre_vif"],
        "removidas_vif": selection["removidas_vif"],
        "vif_final": selection["vif_final"],
        "variaveis_selecionadas": selection["variaveis_selecionadas"],
    }
    write_excel_report(excel_path, sheets)

    selected = selection["variaveis_selecionadas"]
    if isinstance(selected, pd.DataFrame):
        selected.to_csv(csv_path, index=False, encoding="utf-8-sig")
    else:
        pd.DataFrame().to_csv(csv_path, index=False, encoding="utf-8-sig")

    write_markdown_report(
        md_path, cfg, df, target_col, created_targets,
        numeric_desc, categorical_desc, quality, selection
    )
    write_metadata(metadata_path, cfg, target_col, created_targets, {
        "excel_report": str(excel_path),
        "markdown_report": str(md_path),
        "selected_variables_csv": str(csv_path),
        "metadata_json": str(metadata_path),
    })

    print("[OK] Análise concluída.")
    print(f"[OK] Relatório Excel: {excel_path}")
    print(f"[OK] Relatório Markdown: {md_path}")
    print(f"[OK] Variáveis selecionadas: {csv_path}")
    print(f"[OK] Metadados: {metadata_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
