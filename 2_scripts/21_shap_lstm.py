#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SHAP para modelo LSTM AutoML.

Este script foi preparado para os anexos:
  - lstm_automl.keras
  - preprocessadores.joblib
  - base_final.xlsx

O arquivo optuna_study_ROA.joblib não é necessário para o SHAP, pois o arquivo
preprocessadores_ROA.joblib já contém: lista de features, imputador, scaler de X,
scaler de y, argumentos de treino e melhores hiperparâmetros, incluindo seq_len.

Saídas principais:
  - shap_values_flat.npy
  - shap_values_3d.npy
  - shap_base_values.npy
  - metadados_amostras_shap.csv
  - shap_importance_lag_feature.csv
  - shap_importance_feature_aggregated.csv
  - shap_importance_by_lag.csv
  - shap_bar_flat_top.png
  - shap_beeswarm_flat_top.png
  - shap_bar_feature_aggregated_top.png
  - shap_heatmap_feature_lag_top.png
  - relatorio_shap.md

Observação metodológica:
  O script usa SHAP model-agnostic por permutação por padrão. Isso é mais robusto
  para modelos LSTM/Keras salvos em .keras, pois explica uma função de predição que
  recebe a sequência achatada, reconstrói a entrada 3D da LSTM e retorna a predição
  em escala original quando y_scaler estiver disponível.
  
  python 21_shap_lstm.py --base bases/base_final_winsorizada.xlsx --modelo "outputs/modelos/AM2 - LSTM/liquidez_receitas/ROA/lstm_automl_ROA.keras" --preprocessadores "outputs/modelos/AM2 - LSTM/liquidez_receitas/ROA/preprocessadores_ROA.joblib" --output-dir outputs/SHAP/LSTM/liquidez_receitas/ROA
  python 21_shap_lstm.py --base bases/base_final_winsorizada.xlsx --modelo "outputs/modelos/AM2 - LSTM/exaustivo/ROE/lstm_automl_ROE.keras" --preprocessadores "outputs/modelos/AM2 - LSTM/exaustivo/ROE/preprocessadores_ROE.joblib" --output-dir outputs/SHAP/LSTM/exaustivo/ROE
  python 21_shap_lstm.py --base bases/base_final_winsorizada.xlsx --modelo "outputs/modelos/AM2 - LSTM/exaustivo/NIM/lstm_automl_NIM.keras" --preprocessadores "outputs/modelos/AM2 - LSTM/exaustivo/NIM/preprocessadores_NIM.joblib" --output-dir outputs/SHAP/LSTM/exaustivo/NIM
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import warnings
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd

# Backend não interativo para salvar figuras em execução por terminal/servidor.
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calcula SHAP para uma LSTM Keras treinada para ROA em painel temporal."
    )
    parser.add_argument("--base", default="base_final.xlsx", help="Caminho da base Excel.")
    parser.add_argument("--modelo", default="lstm_automl_ROA.keras", help="Caminho do modelo Keras .keras.")
    parser.add_argument(
        "--preprocessadores",
        default="preprocessadores_ROA.joblib",
        help="Caminho do joblib com imputador, scalers, features e parâmetros.",
    )
    parser.add_argument("--sheet", default=None, help="Aba da planilha. Se omitido, usa args['sheet'] ou 0.")
    parser.add_argument("--target", default=None, help="Variável alvo. Se omitido, usa args['target'] ou ROA.")
    parser.add_argument("--entity-col", default=None, help="Coluna da instituição. Se omitido, usa args['entity_col'].")
    parser.add_argument("--time-col", default=None, help="Coluna temporal. Se omitido, usa args['time_col'].")
    parser.add_argument("--horizon", type=int, default=None, help="Horizonte usado no treino. Se omitido, usa args['horizon'].")
    parser.add_argument("--seq-len", type=int, default=None, help="Tamanho da janela temporal. Se omitido, usa best_params['seq_len'].")
    parser.add_argument(
        "--scope",
        choices=["test", "all"],
        default="test",
        help="Amostras explicadas: período de teste inferido pelos últimos períodos ou todas as sequências.",
    )
    parser.add_argument(
        "--test-periods",
        type=int,
        default=None,
        help="Número de períodos finais tratados como teste. Se omitido, usa args['test_periods'] ou 8.",
    )
    parser.add_argument("--background-size", type=int, default=40, help="Número de sequências de background SHAP.")
    parser.add_argument("--explain-size", type=int, default=80, help="Número máximo de sequências explicadas.")
    parser.add_argument("--random-state", type=int, default=42, help="Semente para amostragem.")
    parser.add_argument(
        "--explainer",
        choices=["permutation", "kernel"],
        default="permutation",
        help="Tipo de explicador model-agnostic. Permutation é o padrão recomendado.",
    )
    parser.add_argument(
        "--max-evals",
        default="auto",
        help="Permutations: avaliações por amostra. 'auto' usa pelo menos 2*p+1, onde p=seq_len*n_features.",
    )
    parser.add_argument(
        "--kernel-nsamples",
        default="auto",
        help="KernelExplainer: número de amostras. Use 'auto' ou inteiro.",
    )
    parser.add_argument("--predict-batch-size", type=int, default=256, help="Batch size do model.predict.")
    parser.add_argument("--shap-batch-size", default="auto", help="Batch size interno do SHAP por permutação.")
    parser.add_argument("--top-n", type=int, default=25, help="Número de variáveis nos gráficos principais.")
    parser.add_argument("--output-dir", default="outputs_shap_roa", help="Diretório de saída.")
    parser.add_argument(
        "--no-inverse-y",
        action="store_true",
        help="Não inverter y_scaler; mantém SHAP na escala padronizada de saída do modelo.",
    )
    parser.add_argument(
        "--save-explainer-data",
        action="store_true",
        help="Salva X_background_flat.npy e X_explain_flat.npy. Pode expor dados transformados.",
    )
    return parser.parse_args()


def load_keras_model(model_path: str):
    """Carrega modelo Keras/TensorFlow de forma tolerante a versões."""
    last_error = None
    for loader_name in ("tensorflow.keras", "keras"):
        try:
            if loader_name == "tensorflow.keras":
                import tensorflow as tf  # type: ignore
                return tf.keras.models.load_model(model_path, compile=False)
            else:
                import keras  # type: ignore
                try:
                    return keras.models.load_model(model_path, compile=False, safe_mode=False)
                except TypeError:
                    return keras.models.load_model(model_path, compile=False)
        except Exception as exc:  # pragma: no cover - depende do ambiente local
            last_error = exc
    raise RuntimeError(
        "Não foi possível carregar o modelo Keras. Instale tensorflow ou keras compatível. "
        f"Erro original: {repr(last_error)}"
    )


def get_from_preproc(preproc: Dict[str, Any], key: str, default: Any = None) -> Any:
    args = preproc.get("args", {}) if isinstance(preproc, dict) else {}
    best_params = preproc.get("best_params", {}) if isinstance(preproc, dict) else {}
    if key in preproc:
        return preproc[key]
    if key in args:
        return args[key]
    if key in best_params:
        return best_params[key]
    return default


def resolve_config(args: argparse.Namespace, preproc: Dict[str, Any]) -> Dict[str, Any]:
    train_args = preproc.get("args", {})
    best_params = preproc.get("best_params", {})
    config = {
        "sheet": args.sheet if args.sheet is not None else train_args.get("sheet", 0),
        "target": args.target or train_args.get("target", "ROA"),
        "entity_col": args.entity_col or train_args.get("entity_col", "id_entidade"),
        "time_col": args.time_col or train_args.get("time_col", "AnoMes_ord"),
        "horizon": args.horizon if args.horizon is not None else int(train_args.get("horizon", 1)),
        "seq_len": args.seq_len if args.seq_len is not None else int(best_params.get("seq_len", 4)),
        "test_periods": args.test_periods if args.test_periods is not None else int(train_args.get("test_periods", 8)),
    }
    return config


def coerce_sheet_value(value: Any) -> Any:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    text = str(value)
    if text.isdigit():
        return int(text)
    return text


def read_base_excel(path: str, sheet: Any) -> pd.DataFrame:
    sheet_value = coerce_sheet_value(sheet)
    return pd.read_excel(path, sheet_name=sheet_value)


def validate_inputs(
    df: pd.DataFrame,
    features: List[str],
    target: str,
    entity_col: str,
    time_col: str,
) -> None:
    required = [entity_col, time_col] + features
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(
            "A base não contém as colunas necessárias para reconstruir as sequências: "
            + ", ".join(missing)
        )
    if target not in df.columns:
        warnings.warn(
            f"A coluna alvo '{target}' não está na base. O SHAP será calculado sem y_real nos metadados.",
            RuntimeWarning,
        )


def transform_features(
    df_sorted: pd.DataFrame,
    features: List[str],
    imputer: Any,
    x_scaler: Any,
) -> np.ndarray:
    X_raw = df_sorted[features].copy()
    X_raw = X_raw.replace([np.inf, -np.inf], np.nan)

    X_imp = imputer.transform(X_raw) if imputer is not None else X_raw.to_numpy(dtype=float)
    X_scaled = x_scaler.transform(X_imp) if x_scaler is not None else X_imp
    return np.asarray(X_scaled, dtype=np.float32)


def build_sequences(
    df: pd.DataFrame,
    X_scaled: np.ndarray,
    features: List[str],
    target: str,
    entity_col: str,
    time_col: str,
    seq_len: int,
    horizon: int,
) -> Tuple[np.ndarray, pd.DataFrame]:
    """Reconstrói sequências por instituição, respeitando ordenação temporal."""
    sequences: List[np.ndarray] = []
    rows_meta: List[Dict[str, Any]] = []

    for entity, group in df.groupby(entity_col, sort=False):
        pos = group.index.to_numpy()
        if len(pos) < seq_len + horizon:
            continue

        times = group[time_col].to_numpy()
        y_values = group[target].to_numpy() if target in group.columns else np.array([np.nan] * len(group))

        # end_local é a posição final da janela de entrada; target_local é o período futuro explicado.
        for end_local in range(seq_len - 1, len(pos) - horizon):
            start_local = end_local - seq_len + 1
            target_local = end_local + horizon
            seq_positions = pos[start_local : end_local + 1]
            target_position = pos[target_local]

            sequences.append(X_scaled[seq_positions, :])
            rows_meta.append(
                {
                    entity_col: entity,
                    "seq_start_time": times[start_local],
                    "seq_end_time": times[end_local],
                    "target_time": times[target_local],
                    "row_target_index": int(target_position),
                    "y_real": y_values[target_local] if target in group.columns else np.nan,
                }
            )

    if not sequences:
        raise ValueError(
            "Nenhuma sequência foi criada. Verifique seq_len, horizon, entity_col e time_col."
        )

    X_seq = np.stack(sequences).astype(np.float32)
    meta = pd.DataFrame(rows_meta)
    return X_seq, meta


def sample_indices(pool_size: int, sample_size: int, rng: np.random.Generator) -> np.ndarray:
    if pool_size <= 0:
        raise ValueError("Pool de amostragem vazio.")
    n = min(pool_size, max(1, sample_size))
    return np.sort(rng.choice(pool_size, size=n, replace=False))


def split_background_and_explain(
    X_seq: np.ndarray,
    meta: pd.DataFrame,
    scope: str,
    test_periods: int,
    background_size: int,
    explain_size: int,
    random_state: int,
) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(random_state)
    unique_times = np.array(sorted(pd.unique(meta["target_time"])))

    if scope == "test" and len(unique_times) > test_periods:
        test_times = set(unique_times[-test_periods:])
        explain_mask = meta["target_time"].isin(test_times).to_numpy()
        background_mask = ~explain_mask
    else:
        explain_mask = np.ones(len(meta), dtype=bool)
        background_mask = np.ones(len(meta), dtype=bool)

    explain_pool = np.where(explain_mask)[0]
    background_pool = np.where(background_mask)[0]

    # Fallback para bases pequenas.
    if len(background_pool) == 0:
        background_pool = np.arange(len(meta))
    if len(explain_pool) == 0:
        explain_pool = np.arange(len(meta))

    bg_sel_local = sample_indices(len(background_pool), background_size, rng)
    ex_sel_local = sample_indices(len(explain_pool), explain_size, rng)

    bg_idx = background_pool[bg_sel_local]
    ex_idx = explain_pool[ex_sel_local]

    return X_seq[bg_idx], X_seq[ex_idx], meta.iloc[bg_idx].copy(), meta.iloc[ex_idx].copy()


def make_flat_feature_names(features: List[str], seq_len: int) -> List[str]:
    names: List[str] = []
    for step in range(seq_len):
        distance = seq_len - 1 - step
        lag_label = "t" if distance == 0 else f"t-{distance}"
        for feat in features:
            names.append(f"{lag_label}__{feat}")
    return names


def lag_labels(seq_len: int) -> List[str]:
    out = []
    for step in range(seq_len):
        distance = seq_len - 1 - step
        out.append("t" if distance == 0 else f"t-{distance}")
    return out


def inverse_y_if_possible(pred: np.ndarray, y_scaler: Any, inverse_y: bool) -> np.ndarray:
    pred_2d = np.asarray(pred).reshape(-1, 1)
    if inverse_y and y_scaler is not None:
        try:
            return y_scaler.inverse_transform(pred_2d).reshape(-1)
        except Exception as exc:
            warnings.warn(
                f"Falha ao aplicar inverse_transform no y_scaler; mantendo escala do modelo. Erro: {exc}",
                RuntimeWarning,
            )
    return pred_2d.reshape(-1)


def run_shap(
    model: Any,
    X_background: np.ndarray,
    X_explain: np.ndarray,
    features: List[str],
    y_scaler: Any,
    inverse_y: bool,
    args: argparse.Namespace,
) -> Any:
    import shap

    seq_len = X_explain.shape[1]
    n_features = X_explain.shape[2]
    n_flat = seq_len * n_features

    X_background_flat = X_background.reshape(X_background.shape[0], n_flat).astype(np.float32)
    X_explain_flat = X_explain.reshape(X_explain.shape[0], n_flat).astype(np.float32)

    def predict_flat(X_flat: np.ndarray) -> np.ndarray:
        X_arr = np.asarray(X_flat, dtype=np.float32)
        if X_arr.ndim == 1:
            X_arr = X_arr.reshape(1, -1)
        X_3d = X_arr.reshape(X_arr.shape[0], seq_len, n_features)
        pred = model.predict(X_3d, verbose=0, batch_size=args.predict_batch_size)
        return inverse_y_if_possible(pred, y_scaler=y_scaler, inverse_y=inverse_y)

    flat_names = make_flat_feature_names(features, seq_len)

    if args.explainer == "permutation":
        masker = shap.maskers.Independent(X_background_flat, max_samples=X_background_flat.shape[0])
        explainer = shap.PermutationExplainer(
            predict_flat,
            masker,
            feature_names=flat_names,
            seed=args.random_state,
        )
        if args.max_evals == "auto":
            max_evals = max(2 * n_flat + 1, 500)
        else:
            max_evals = int(args.max_evals)
            min_required = 2 * n_flat + 1
            if max_evals < min_required:
                warnings.warn(
                    f"max_evals={max_evals} é menor que 2*p+1={min_required}; ajustando para {min_required}.",
                    RuntimeWarning,
                )
                max_evals = min_required
        explanation = explainer(
            X_explain_flat,
            max_evals=max_evals,
            batch_size=args.shap_batch_size,
            silent=False,
        )
    else:
        # KernelExplainer é mais lento, mas também model-agnostic.
        explainer = shap.KernelExplainer(predict_flat, X_background_flat, feature_names=flat_names)
        nsamples = args.kernel_nsamples if args.kernel_nsamples == "auto" else int(args.kernel_nsamples)
        values = explainer.shap_values(X_explain_flat, nsamples=nsamples)
        base_values = np.repeat(np.asarray(explainer.expected_value).reshape(-1)[0], X_explain_flat.shape[0])
        explanation = shap.Explanation(
            values=np.asarray(values),
            base_values=base_values,
            data=X_explain_flat,
            feature_names=flat_names,
        )

    return explanation, X_background_flat, X_explain_flat, predict_flat(X_explain_flat)


def normalize_shap_values(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values)
    # Caso saída venha como (n, p, 1), converte para (n, p).
    if arr.ndim == 3 and arr.shape[-1] == 1:
        arr = arr[:, :, 0]
    if arr.ndim != 2:
        raise ValueError(f"Formato inesperado de SHAP values: {arr.shape}")
    return arr


def save_importance_tables(
    shap_values_flat: np.ndarray,
    features: List[str],
    seq_len: int,
    output_dir: Path,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, np.ndarray]:
    n_features = len(features)
    shap_values_3d = shap_values_flat.reshape(shap_values_flat.shape[0], seq_len, n_features)
    lags = lag_labels(seq_len)

    # Importância de cada célula lag-feature.
    rows = []
    mean_abs_by_lag_feature = np.mean(np.abs(shap_values_3d), axis=0)  # (seq_len, n_features)
    mean_by_lag_feature = np.mean(shap_values_3d, axis=0)
    for i_lag, lag in enumerate(lags):
        for j_feat, feat in enumerate(features):
            rows.append(
                {
                    "lag": lag,
                    "feature": feat,
                    "lag_feature": f"{lag}__{feat}",
                    "mean_abs_shap": mean_abs_by_lag_feature[i_lag, j_feat],
                    "mean_shap": mean_by_lag_feature[i_lag, j_feat],
                }
            )
    imp_lag_feature = pd.DataFrame(rows).sort_values("mean_abs_shap", ascending=False)
    imp_lag_feature.insert(0, "rank", np.arange(1, len(imp_lag_feature) + 1))
    imp_lag_feature.to_csv(output_dir / "shap_importance_lag_feature.csv", index=False, encoding="utf-8-sig")

    # Agregação por feature original: soma das importâncias absolutas médias ao longo dos lags.
    shap_feature_sum_per_sample = shap_values_3d.sum(axis=1)  # contribuição total por feature em cada amostra
    imp_feature = pd.DataFrame(
        {
            "feature": features,
            "mean_abs_shap_sum_lags": mean_abs_by_lag_feature.sum(axis=0),
            "mean_abs_of_total_shap_feature": np.mean(np.abs(shap_feature_sum_per_sample), axis=0),
            "mean_total_shap_feature": np.mean(shap_feature_sum_per_sample, axis=0),
        }
    ).sort_values("mean_abs_shap_sum_lags", ascending=False)
    imp_feature.insert(0, "rank", np.arange(1, len(imp_feature) + 1))
    imp_feature.to_csv(output_dir / "shap_importance_feature_aggregated.csv", index=False, encoding="utf-8-sig")

    # Agregação por lag.
    imp_lag = pd.DataFrame(
        {
            "lag": lags,
            "mean_abs_shap_sum_features": mean_abs_by_lag_feature.sum(axis=1),
            "mean_shap_sum_features": mean_by_lag_feature.sum(axis=1),
        }
    ).sort_values("mean_abs_shap_sum_features", ascending=False)
    imp_lag.insert(0, "rank", np.arange(1, len(imp_lag) + 1))
    imp_lag.to_csv(output_dir / "shap_importance_by_lag.csv", index=False, encoding="utf-8-sig")

    return imp_lag_feature, imp_feature, imp_lag, shap_values_3d


def save_plots(
    explanation: Any,
    imp_feature: pd.DataFrame,
    mean_abs_by_lag_feature: np.ndarray,
    features: List[str],
    seq_len: int,
    output_dir: Path,
    top_n: int,
) -> None:
    import shap

    # Gráficos nativos SHAP para as variáveis achatadas lag-feature.
    try:
        plt.figure()
        shap.plots.bar(explanation, max_display=top_n, show=False)
        plt.tight_layout()
        plt.savefig(output_dir / "shap_bar_flat_top.png", dpi=220, bbox_inches="tight")
        plt.close()
    except Exception as exc:
        warnings.warn(f"Falha ao salvar shap_bar_flat_top.png: {exc}", RuntimeWarning)

    try:
        plt.figure()
        shap.plots.beeswarm(explanation, max_display=top_n, show=False)
        plt.tight_layout()
        plt.savefig(output_dir / "shap_beeswarm_flat_top.png", dpi=220, bbox_inches="tight")
        plt.close()
    except Exception as exc:
        warnings.warn(f"Falha ao salvar shap_beeswarm_flat_top.png: {exc}", RuntimeWarning)

    # Barplot agregado por feature original.
    top = imp_feature.head(top_n).sort_values("mean_abs_shap_sum_lags", ascending=True)
    plt.figure(figsize=(11, max(6, 0.35 * len(top))))
    plt.barh(top["feature"], top["mean_abs_shap_sum_lags"])
    plt.xlabel("mean(|SHAP|) somado nos lags")
    plt.ylabel("Feature")
    plt.title("Importância SHAP agregada por variável original")
    plt.tight_layout()
    plt.savefig(output_dir / "shap_bar_feature_aggregated_top.png", dpi=220, bbox_inches="tight")
    plt.close()

    # Heatmap lag x feature para as top features agregadas.
    top_features = imp_feature.head(min(top_n, len(features)))["feature"].tolist()
    top_idx = [features.index(f) for f in top_features]
    heat = mean_abs_by_lag_feature[:, top_idx].T

    plt.figure(figsize=(10, max(6, 0.30 * len(top_features))))
    plt.imshow(heat, aspect="auto")
    plt.colorbar(label="mean(|SHAP|)")
    plt.yticks(np.arange(len(top_features)), top_features)
    plt.xticks(np.arange(seq_len), lag_labels(seq_len))
    plt.xlabel("Defasagem dentro da sequência")
    plt.ylabel("Feature")
    plt.title("Importância SHAP por variável e defasagem temporal")
    plt.tight_layout()
    plt.savefig(output_dir / "shap_heatmap_feature_lag_top.png", dpi=220, bbox_inches="tight")
    plt.close()


def write_report(
    output_dir: Path,
    config: Dict[str, Any],
    args: argparse.Namespace,
    df_shape: Tuple[int, int],
    n_sequences: int,
    n_background: int,
    n_explain: int,
    imp_feature: pd.DataFrame,
    imp_lag: pd.DataFrame,
    elapsed: float,
) -> None:
    top_features = imp_feature.head(15).copy()
    top_lags = imp_lag.copy()

    lines = []
    lines.append("# Relatório SHAP — LSTM AutoML ROA")
    lines.append("")
    lines.append("## Configuração")
    lines.append(f"- Base: `{args.base}`")
    lines.append(f"- Modelo: `{args.modelo}`")
    lines.append(f"- Preprocessadores: `{args.preprocessadores}`")
    lines.append(f"- Target: `{config['target']}`")
    lines.append(f"- Instituição: `{config['entity_col']}`")
    lines.append(f"- Tempo: `{config['time_col']}`")
    lines.append(f"- Horizonte: `{config['horizon']}`")
    lines.append(f"- Comprimento da sequência: `{config['seq_len']}`")
    lines.append(f"- Explainer: `{args.explainer}`")
    lines.append(f"- Escala do output: `{'original do target' if not args.no_inverse_y else 'escala padronizada do modelo'}`")
    lines.append("")
    lines.append("## Amostras")
    lines.append(f"- Dimensão da base: {df_shape[0]} linhas x {df_shape[1]} colunas")
    lines.append(f"- Sequências reconstruídas: {n_sequences}")
    lines.append(f"- Sequências de background: {n_background}")
    lines.append(f"- Sequências explicadas: {n_explain}")
    lines.append("")
    lines.append("## Top 15 variáveis agregadas")
    lines.append("```")
    lines.append(top_features.to_string(index=False))
    lines.append("```")
    lines.append("")
    lines.append("## Importância por defasagem")
    lines.append("```")
    lines.append(top_lags.to_string(index=False))
    lines.append("```")
    lines.append("")
    lines.append("## Arquivos gerados")
    for filename in [
        "shap_values_flat.npy",
        "shap_values_3d.npy",
        "shap_base_values.npy",
        "metadados_amostras_shap.csv",
        "shap_importance_lag_feature.csv",
        "shap_importance_feature_aggregated.csv",
        "shap_importance_by_lag.csv",
        "shap_bar_flat_top.png",
        "shap_beeswarm_flat_top.png",
        "shap_bar_feature_aggregated_top.png",
        "shap_heatmap_feature_lag_top.png",
    ]:
        lines.append(f"- `{filename}`")
    lines.append("")
    lines.append(f"Tempo total de execução: {elapsed:.2f} segundos.")

    (output_dir / "relatorio_shap.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    t0 = time.time()
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    warnings.filterwarnings("default")
    rng = np.random.default_rng(args.random_state)
    np.random.seed(args.random_state)

    print("[1/8] Carregando preprocessadores...")
    preproc = joblib.load(args.preprocessadores)
    if not isinstance(preproc, dict):
        raise TypeError("O arquivo de preprocessadores deveria conter um dict.")

    features = preproc.get("features")
    if not features:
        raise ValueError("O arquivo de preprocessadores não contém a chave 'features'.")
    features = list(features)

    imputer = preproc.get("imputer")
    x_scaler = preproc.get("x_scaler")
    y_scaler = preproc.get("y_scaler")
    config = resolve_config(args, preproc)

    print("[2/8] Lendo base e validando colunas...")
    df = read_base_excel(args.base, config["sheet"])
    validate_inputs(df, features, config["target"], config["entity_col"], config["time_col"])

    df_sorted = df.sort_values([config["entity_col"], config["time_col"]]).reset_index(drop=True)

    print("[3/8] Aplicando imputação/escalonamento e reconstruindo sequências...")
    X_scaled = transform_features(df_sorted, features, imputer, x_scaler)
    X_seq, meta = build_sequences(
        df_sorted,
        X_scaled,
        features=features,
        target=config["target"],
        entity_col=config["entity_col"],
        time_col=config["time_col"],
        seq_len=config["seq_len"],
        horizon=config["horizon"],
    )

    X_background, X_explain, meta_background, meta_explain = split_background_and_explain(
        X_seq,
        meta,
        scope=args.scope,
        test_periods=config["test_periods"],
        background_size=args.background_size,
        explain_size=args.explain_size,
        random_state=args.random_state,
    )

    print(f"      Sequências totais: {len(X_seq)} | background: {len(X_background)} | explicadas: {len(X_explain)}")

    print("[4/8] Carregando modelo Keras...")
    model = load_keras_model(args.modelo)

    print("[5/8] Calculando SHAP...")
    explanation, X_background_flat, X_explain_flat, y_pred_explain = run_shap(
        model=model,
        X_background=X_background,
        X_explain=X_explain,
        features=features,
        y_scaler=y_scaler,
        inverse_y=not args.no_inverse_y,
        args=args,
    )

    print("[6/8] Salvando arrays e metadados...")
    shap_values_flat = normalize_shap_values(explanation.values)
    shap_values_3d = shap_values_flat.reshape(shap_values_flat.shape[0], config["seq_len"], len(features))

    np.save(output_dir / "shap_values_flat.npy", shap_values_flat)
    np.save(output_dir / "shap_values_3d.npy", shap_values_3d)
    np.save(output_dir / "shap_base_values.npy", np.asarray(explanation.base_values))

    if args.save_explainer_data:
        np.save(output_dir / "X_background_flat.npy", X_background_flat)
        np.save(output_dir / "X_explain_flat.npy", X_explain_flat)

    meta_explain = meta_explain.reset_index(drop=True)
    meta_explain["y_pred"] = y_pred_explain
    if "y_real" in meta_explain.columns:
        meta_explain["erro_pred_menos_real"] = meta_explain["y_pred"] - meta_explain["y_real"]
    meta_explain.to_csv(output_dir / "metadados_amostras_shap.csv", index=False, encoding="utf-8-sig")
    meta_background.reset_index(drop=True).to_csv(output_dir / "metadados_background_shap.csv", index=False, encoding="utf-8-sig")

    print("[7/8] Agregando importâncias e gerando gráficos...")
    imp_lag_feature, imp_feature, imp_lag, _ = save_importance_tables(
        shap_values_flat=shap_values_flat,
        features=features,
        seq_len=config["seq_len"],
        output_dir=output_dir,
    )
    mean_abs_by_lag_feature = np.mean(np.abs(shap_values_3d), axis=0)
    save_plots(
        explanation=explanation,
        imp_feature=imp_feature,
        mean_abs_by_lag_feature=mean_abs_by_lag_feature,
        features=features,
        seq_len=config["seq_len"],
        output_dir=output_dir,
        top_n=args.top_n,
    )

    print("[8/8] Salvando relatório e manifesto...")
    manifest = {
        "base": args.base,
        "modelo": args.modelo,
        "preprocessadores": args.preprocessadores,
        "output_dir": str(output_dir),
        "config": config,
        "n_features": len(features),
        "features": features,
        "n_sequences_total": int(len(X_seq)),
        "n_background": int(len(X_background)),
        "n_explain": int(len(X_explain)),
        "explainer": args.explainer,
        "inverse_y": not args.no_inverse_y,
        "random_state": args.random_state,
    }
    (output_dir / "manifest_shap.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    elapsed = time.time() - t0
    write_report(
        output_dir=output_dir,
        config=config,
        args=args,
        df_shape=df.shape,
        n_sequences=len(X_seq),
        n_background=len(X_background),
        n_explain=len(X_explain),
        imp_feature=imp_feature,
        imp_lag=imp_lag,
        elapsed=elapsed,
    )

    print("\nConcluído.")
    print(f"Diretório de saída: {output_dir.resolve()}")
    print("Principais arquivos:")
    print(f"  - {output_dir / 'relatorio_shap.md'}")
    print(f"  - {output_dir / 'shap_importance_feature_aggregated.csv'}")
    print(f"  - {output_dir / 'shap_heatmap_feature_lag_top.png'}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nERRO: {exc}", file=sys.stderr)
        raise
