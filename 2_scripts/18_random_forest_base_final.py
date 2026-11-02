#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Random Forest para modelagem de rentabilidade bancária em painel.

Arquivo esperado: base_final.xlsx
Base observada: colunas como AnoMes_ord, id_entidade, ROA, ROE, NIM,
indicadores de liquidez, controles contábeis, macroeconômicos e dummies.

python 18_random_forest_base_final.py --input bases/base_final_winsorizada.xlsx --target ROA --output-dir "outputs/modelos/AM1 - Random forest/geral/rf_geral_roa" --drop-cols "trimestre,ativo_total,disponibilidades,permanente_ajustado,patrimonio_liquido,passivo_total,lucro_liquido,captacoes,depositos,depositos_a_prazo,depositos_a_vista,despesas_administrativas,despesas_tributarias,despesas_de_captacao,despesas_de_intermediacao_financeira,despesas_de_pessoal,operacoes_de_credito,operacoes_de_credito,receitas_de_intermediacao_financeira,rendas_de_operacoes_com_TVM,rendas_de_operacoes_de_credito,rendas_de_prestacao_de_servicos,rendas_de_tarifas_bancarias,resultado_de_intermediacao_financeira,resultado_de_provisao_para_creditos_de_dificil_liquidacao,provisao_sobre_operacoes_de_credito,ativos_sobre_captacoes,operacoes_de_credito_sobre_depositos,operacoes_de_credito_sobre_ativo_total,gap_de_funding,indice_de_basileia_dec,ipca_media_trimestre_dec,ipca_soma_trimestre_dec,ipca_fim_trimestre_dec,pib_indice_sa,market_share_dec,hhi_contribuicao_dec,ativo_total_log,disponibilidades_log,permanente_ajustado_log,captacoes_log,depositos_log,depositos_a_prazo_log,depositos_a_vista_log,operacoes_de_credito_log,despesas_tributarias_sobre_receitas,despesas_de_pessoal_sobre_receitas,operacoes_de_credito_ativo_total,provisoes_de_credito_sobre_ativo_total,rendas_de_operacoes_de_credito_sobre_ativo_total"
python 18_random_forest_base_final.py --input bases/base_final_winsorizada.xlsx --target ROE --output-dir "outputs/modelos/AM1 - Random forest/geral/rf_geral_roe" --drop-cols "trimestre,ativo_total,disponibilidades,permanente_ajustado,patrimonio_liquido,passivo_total,lucro_liquido,captacoes,depositos,depositos_a_prazo,depositos_a_vista,despesas_administrativas,despesas_tributarias,despesas_de_captacao,despesas_de_intermediacao_financeira,despesas_de_pessoal,operacoes_de_credito,operacoes_de_credito,receitas_de_intermediacao_financeira,rendas_de_operacoes_com_TVM,rendas_de_operacoes_de_credito,rendas_de_prestacao_de_servicos,rendas_de_tarifas_bancarias,resultado_de_intermediacao_financeira,resultado_de_provisao_para_creditos_de_dificil_liquidacao,provisao_sobre_operacoes_de_credito,ativos_sobre_captacoes,operacoes_de_credito_sobre_depositos,operacoes_de_credito_sobre_ativo_total,gap_de_funding,indice_de_basileia_dec,ipca_media_trimestre_dec,ipca_soma_trimestre_dec,ipca_fim_trimestre_dec,pib_indice_sa,market_share_dec,hhi_contribuicao_dec,ativo_total_log,disponibilidades_log,permanente_ajustado_log,captacoes_log,depositos_log,depositos_a_prazo_log,depositos_a_vista_log,operacoes_de_credito_log,despesas_tributarias_sobre_receitas,despesas_de_pessoal_sobre_receitas,operacoes_de_credito_ativo_total,provisoes_de_credito_sobre_ativo_total,rendas_de_operacoes_de_credito_sobre_ativo_total"
python 18_random_forest_base_final.py --input bases/base_final_winsorizada.xlsx --target NIM --output-dir "outputs/modelos/AM1 - Random forest/geral/rf_geral_nim" --drop-cols "trimestre,ativo_total,disponibilidades,permanente_ajustado,patrimonio_liquido,passivo_total,lucro_liquido,captacoes,depositos,depositos_a_prazo,depositos_a_vista,despesas_administrativas,despesas_tributarias,despesas_de_captacao,despesas_de_intermediacao_financeira,despesas_de_pessoal,operacoes_de_credito,operacoes_de_credito,receitas_de_intermediacao_financeira,rendas_de_operacoes_com_TVM,rendas_de_operacoes_de_credito,rendas_de_prestacao_de_servicos,rendas_de_tarifas_bancarias,resultado_de_intermediacao_financeira,resultado_de_provisao_para_creditos_de_dificil_liquidacao,provisao_sobre_operacoes_de_credito,ativos_sobre_captacoes,operacoes_de_credito_sobre_depositos,operacoes_de_credito_sobre_ativo_total,gap_de_funding,indice_de_basileia_dec,ipca_media_trimestre_dec,ipca_soma_trimestre_dec,ipca_fim_trimestre_dec,pib_indice_sa,market_share_dec,hhi_contribuicao_dec,ativo_total_log,disponibilidades_log,permanente_ajustado_log,captacoes_log,depositos_log,depositos_a_prazo_log,depositos_a_vista_log,operacoes_de_credito_log,despesas_tributarias_sobre_receitas,despesas_de_pessoal_sobre_receitas,operacoes_de_credito_ativo_total,provisoes_de_credito_sobre_ativo_total,rendas_de_operacoes_de_credito_sobre_ativo_total"

Saídas geradas em --output-dir:
    - metricas_random_forest_<target>.csv
    - importancia_variaveis_<target>.csv
    - permutation_importance_<target>.csv, se --perm-repeats > 0
    - predicoes_random_forest_<target>.xlsx
    - modelo_random_forest_<target>.joblib
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Iterable, Sequence

import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


TARGETS_RENTABILIDADE = {"ROA", "ROE", "NIM"}

# Componentes que podem gerar vazamento informacional por entrarem diretamente
# no cálculo ou por serem muito próximos da variável-alvo. O script remove por
# padrão; use --keep-leakage-components se quiser mantê-los conscientemente.
LEAKAGE_COMPONENTS = {
    "ROA": [
        "ROA",
        "ROE",
        "NIM",
        "lucro_liquido",
        "ativo_total",
        "ativo_total_log",
        "ativos_totais_banco_brl",
    ],
    "ROE": [
        "ROA",
        "ROE",
        "NIM",
        "lucro_liquido",
        "patrimonio_liquido",
        "patrimonio_liquido_log",
    ],
    "NIM": [
        "ROA",
        "ROE",
        "NIM",
        "resultado_de_intermediacao_financeira",
        "resultado_de_intermediacao_financeira_sobre_ativo_total",
        "receitas_de_intermediacao_financeira",
        "receitas_de_intermediacao_financeira_sobre_ativo_total",
        "ativo_total",
        "ativo_total_log",
        "ativos_totais_banco_brl",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Executa Random Forest Regressor em base bancária em painel."
    )
    parser.add_argument("--input", required=True, help="Caminho do arquivo .xlsx de entrada.")
    parser.add_argument("--sheet", default=0, help="Nome ou índice da aba. Padrão: 0.")
    parser.add_argument(
        "--target",
        default="ROA",
        choices=sorted(TARGETS_RENTABILIDADE),
        help="Variável dependente. Padrão: ROA.",
    )
    parser.add_argument("--time-col", default="AnoMes_ord", help="Coluna temporal.")
    parser.add_argument("--id-col", default="id_entidade", help="Coluna de instituição.")
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.20,
        help="Proporção do teste. No split temporal, reserva os últimos períodos. Padrão: 0.20.",
    )
    parser.add_argument(
        "--split",
        choices=["temporal", "random"],
        default="temporal",
        help="Tipo de divisão treino/teste. Padrão recomendado para painel: temporal.",
    )
    parser.add_argument(
        "--cv",
        type=int,
        default=5,
        help="Número de folds na validação cruzada. Padrão: 5.",
    )
    parser.add_argument(
        "--n-iter",
        type=int,
        default=40,
        help="Número de combinações no RandomizedSearchCV. Padrão: 40.",
    )
    parser.add_argument(
        "--n-estimators",
        type=int,
        default=500,
        help="Número de árvores quando --no-tuning for usado e valor inicial do modelo. Padrão: 500.",
    )
    parser.add_argument(
        "--perm-repeats",
        type=int,
        default=10,
        help="Repetições da permutation importance. Use 0 para pular. Padrão: 10.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Semente de reprodutibilidade. Padrão: 42.",
    )
    parser.add_argument(
        "--output-dir",
        default="resultados_random_forest",
        help="Diretório de saída. Padrão: resultados_random_forest.",
    )
    parser.add_argument(
        "--drop-cols",
        default="",
        help=" --drop-cols Colunas extras para remover, separadas por vírgula.",
    )
    parser.add_argument(
        "--encode-id",
        action="store_true",
        help="Inclui id_entidade como variável categórica. Por padrão, a coluna é removida.",
    )
    parser.add_argument(
        "--keep-leakage-components",
        action="store_true",
        help="Mantém componentes contábeis próximos ao cálculo do alvo. Use apenas se for metodologicamente justificado.",
    )
    parser.add_argument(
        "--no-tuning",
        action="store_true",
        help="Treina Random Forest com parâmetros padrão, sem RandomizedSearchCV.",
    )
    return parser.parse_args()


def normalize_sheet_arg(sheet_arg: str):
    """Converte índice de aba em inteiro quando possível."""
    try:
        return int(sheet_arg)
    except (TypeError, ValueError):
        return sheet_arg


def to_numeric_when_possible(df: pd.DataFrame, protected_cols: Iterable[str]) -> pd.DataFrame:
    """Converte colunas object para numéricas quando a conversão for majoritariamente válida."""
    protected = set(protected_cols)
    out = df.copy()
    for col in out.columns:
        if col in protected:
            continue
        if out[col].dtype == "object":
            converted = pd.to_numeric(out[col], errors="coerce")
            non_na_original = out[col].notna().sum()
            non_na_converted = converted.notna().sum()
            if non_na_original == 0 or non_na_converted / max(non_na_original, 1) >= 0.90:
                out[col] = converted
    return out


def safe_mape(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    y_true_arr = np.asarray(y_true, dtype=float)
    y_pred_arr = np.asarray(y_pred, dtype=float)
    mask = np.abs(y_true_arr) > 1e-12
    if mask.sum() == 0:
        return np.nan
    return float(np.mean(np.abs((y_true_arr[mask] - y_pred_arr[mask]) / y_true_arr[mask])))


def adjusted_r2(r2: float, n_obs: int, n_features: int) -> float:
    if n_obs <= n_features + 1:
        return np.nan
    return float(1 - (1 - r2) * (n_obs - 1) / (n_obs - n_features - 1))


def temporal_train_test_split(
    df: pd.DataFrame, time_col: str, test_size: float
) -> tuple[pd.DataFrame, pd.DataFrame, str | int | float]:
    """Separa os últimos períodos como teste, preservando a lógica temporal."""
    periods = np.array(sorted(df[time_col].dropna().unique()))
    if len(periods) < 3:
        raise ValueError("Poucos períodos disponíveis para split temporal.")

    n_test_periods = max(1, int(math.ceil(len(periods) * test_size)))
    cutoff = periods[-n_test_periods]

    train_df = df[df[time_col] < cutoff].copy()
    test_df = df[df[time_col] >= cutoff].copy()

    if train_df.empty or test_df.empty:
        raise ValueError("Split temporal gerou treino ou teste vazio. Ajuste --test-size.")

    return train_df, test_df, cutoff


def build_feature_matrix(
    df: pd.DataFrame,
    target: str,
    time_col: str,
    id_col: str,
    drop_cols: list[str],
    encode_id: bool,
    keep_leakage_components: bool,
) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    """Define X e y com remoções de identificadores e possíveis vazamentos."""
    if target not in df.columns:
        raise ValueError(f"Target '{target}' não encontrada. Colunas disponíveis: {list(df.columns)}")

    y = pd.to_numeric(df[target], errors="coerce")

    cols_to_drop = set(drop_cols)
    cols_to_drop.add(target)

    # Remove outras medidas de rentabilidade para evitar que o modelo 'preveja' ROA usando ROE/NIM etc.
    cols_to_drop.update(TARGETS_RENTABILIDADE - {target})

    if not keep_leakage_components:
        cols_to_drop.update(LEAKAGE_COMPONENTS.get(target, []))

    # A coluna temporal é usada para validação temporal e não como preditora por padrão.
    cols_to_drop.add(time_col)

    if not encode_id:
        cols_to_drop.add(id_col)

    # Remove apenas colunas existentes.
    existing_drop = [c for c in cols_to_drop if c in df.columns]
    X = df.drop(columns=existing_drop, errors="ignore")

    # Remove colunas totalmente vazias ou constantes, pois não agregam informação.
    nunique = X.nunique(dropna=True)
    constant_cols = nunique[nunique <= 1].index.tolist()
    X = X.drop(columns=constant_cols, errors="ignore")

    removed_cols = sorted(set(existing_drop + constant_cols))
    return X, y, removed_cols


def make_preprocessor(X: pd.DataFrame) -> tuple[ColumnTransformer, list[str], list[str]]:
    numeric_features = X.select_dtypes(include=[np.number, "bool"]).columns.tolist()
    categorical_features = [c for c in X.columns if c not in numeric_features]

    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
        ]
    )

    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, numeric_features),
            ("cat", categorical_pipeline, categorical_features),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )
    return preprocessor, numeric_features, categorical_features


def get_feature_names(preprocessor: ColumnTransformer) -> list[str]:
    try:
        return preprocessor.get_feature_names_out().tolist()
    except Exception:
        return [f"feature_{i}" for i in range(len(preprocessor.transformers_))]


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {input_path.resolve()}")

    sheet = normalize_sheet_arg(args.sheet)
    df = pd.read_excel(input_path, sheet_name=sheet)
    df.columns = [str(c).strip() for c in df.columns]

    if args.time_col not in df.columns:
        raise ValueError(f"Coluna temporal '{args.time_col}' não encontrada.")
    if args.id_col not in df.columns:
        print(f"Aviso: coluna de ID '{args.id_col}' não encontrada. O script seguirá sem ela.")

    df = to_numeric_when_possible(df, protected_cols=[args.id_col])
    df[args.target] = pd.to_numeric(df[args.target], errors="coerce")
    df = df.dropna(subset=[args.target, args.time_col]).copy()
    df = df.sort_values([args.time_col, args.id_col] if args.id_col in df.columns else [args.time_col])

    extra_drop_cols = [c.strip() for c in args.drop_cols.split(",") if c.strip()]

    X_all, y_all, removed_cols = build_feature_matrix(
        df=df,
        target=args.target,
        time_col=args.time_col,
        id_col=args.id_col,
        drop_cols=extra_drop_cols,
        encode_id=args.encode_id,
        keep_leakage_components=args.keep_leakage_components,
    )

    model_df = pd.concat(
        [df[[args.time_col] + ([args.id_col] if args.id_col in df.columns else [])].reset_index(drop=True),
         X_all.reset_index(drop=True),
         y_all.reset_index(drop=True).rename(args.target)],
        axis=1,
    )
    model_df = model_df.dropna(subset=[args.target]).copy()

    X_all = model_df[X_all.columns]
    y_all = model_df[args.target]

    if args.split == "temporal":
        train_df, test_df, cutoff = temporal_train_test_split(model_df, args.time_col, args.test_size)
        X_train = train_df[X_all.columns]
        y_train = train_df[args.target]
        X_test = test_df[X_all.columns]
        y_test = test_df[args.target]
        split_info = {"tipo": "temporal", "primeiro_periodo_teste": str(cutoff)}
    else:
        train_idx, test_idx = train_test_split(
            np.arange(len(model_df)),
            test_size=args.test_size,
            random_state=args.random_state,
            shuffle=True,
        )
        train_df = model_df.iloc[train_idx].copy()
        test_df = model_df.iloc[test_idx].copy()
        X_train = train_df[X_all.columns]
        y_train = train_df[args.target]
        X_test = test_df[X_all.columns]
        y_test = test_df[args.target]
        split_info = {"tipo": "random", "test_size": args.test_size}

    preprocessor, numeric_features, categorical_features = make_preprocessor(X_train)

    rf = RandomForestRegressor(
        n_estimators=args.n_estimators,
        random_state=args.random_state,
        n_jobs=-1,
        bootstrap=True,
        oob_score=True,
    )

    pipeline = Pipeline(
        steps=[
            ("preprocess", preprocessor),
            ("model", rf),
        ]
    )

    if args.no_tuning:
        best_model = pipeline.fit(X_train, y_train)
        best_params = best_model.get_params()
        cv_best_score = np.nan
    else:
        param_distributions = {
            "model__n_estimators": [200, 300, 500, 700, 1000],
            "model__max_depth": [None, 3, 5, 8, 12, 16, 24],
            "model__min_samples_split": [2, 4, 6, 10, 15],
            "model__min_samples_leaf": [1, 2, 3, 5, 8],
            "model__max_features": ["sqrt", "log2", 0.30, 0.50, 0.70, 1.0],
        }

        if args.split == "temporal":
            cv = TimeSeriesSplit(n_splits=max(2, args.cv))
        else:
            cv = max(2, args.cv)

        search = RandomizedSearchCV(
            estimator=pipeline,
            param_distributions=param_distributions,
            n_iter=args.n_iter,
            scoring="neg_root_mean_squared_error",
            cv=cv,
            random_state=args.random_state,
            n_jobs=-1,
            verbose=1,
            refit=True,
        )
        search.fit(X_train, y_train)
        best_model = search.best_estimator_
        best_params = search.best_params_
        cv_best_score = float(search.best_score_)

        cv_results = pd.DataFrame(search.cv_results_).sort_values("rank_test_score")
        cv_results.to_csv(output_dir / f"cv_results_random_forest_{args.target}.csv", index=False)

    y_pred_train = best_model.predict(X_train)
    y_pred_test = best_model.predict(X_test)

    rmse_train = float(np.sqrt(mean_squared_error(y_train, y_pred_train)))
    rmse_test = float(np.sqrt(mean_squared_error(y_test, y_pred_test)))
    mae_train = float(mean_absolute_error(y_train, y_pred_train))
    mae_test = float(mean_absolute_error(y_test, y_pred_test))
    r2_train = float(r2_score(y_train, y_pred_train))
    r2_test = float(r2_score(y_test, y_pred_test))

    metrics = {
        "target": args.target,
        "n_obs_total": int(len(model_df)),
        "n_obs_train": int(len(X_train)),
        "n_obs_test": int(len(X_test)),
        "n_features_original": int(X_all.shape[1]),
        "split": split_info,
        "rmse_train": rmse_train,
        "rmse_test": rmse_test,
        "mae_train": mae_train,
        "mae_test": mae_test,
        "mape_train": safe_mape(y_train, y_pred_train),
        "mape_test": safe_mape(y_test, y_pred_test),
        "r2_train": r2_train,
        "r2_test": r2_test,
        "r2_ajustado_train": adjusted_r2(r2_train, len(X_train), X_all.shape[1]),
        "r2_ajustado_test": adjusted_r2(r2_test, len(X_test), X_all.shape[1]),
        "cv_best_score_neg_rmse": cv_best_score,
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
        "removed_columns": removed_cols,
        "best_params": best_params,
    }

    pd.json_normalize(metrics).to_csv(output_dir / f"metricas_random_forest_{args.target}.csv", index=False)
    with open(output_dir / f"metricas_random_forest_{args.target}.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2, default=str)

    fitted_preprocessor = best_model.named_steps["preprocess"]
    fitted_rf = best_model.named_steps["model"]
    feature_names = get_feature_names(fitted_preprocessor)

    impurity_importance = pd.DataFrame(
        {
            "variavel": feature_names,
            "importancia_gini_mse": fitted_rf.feature_importances_,
        }
    ).sort_values("importancia_gini_mse", ascending=False)
    impurity_importance.to_csv(output_dir / f"importancia_variaveis_{args.target}.csv", index=False)

    # Permutation importance no teste: interpretação mais conservadora para dissertação.
    # Pode ser custosa; use --perm-repeats 0 para pular.
    if args.perm_repeats > 0:
        perm = permutation_importance(
            best_model,
            X_test,
            y_test,
            n_repeats=args.perm_repeats,
            random_state=args.random_state,
            scoring="neg_root_mean_squared_error",
            n_jobs=-1,
        )
        perm_importance = pd.DataFrame(
            {
                "variavel": X_test.columns,
                "permutation_importance_mean_neg_rmse": perm.importances_mean,
                "permutation_importance_std_neg_rmse": perm.importances_std,
            }
        ).sort_values("permutation_importance_mean_neg_rmse", ascending=False)
        perm_importance.to_csv(output_dir / f"permutation_importance_{args.target}.csv", index=False)
    else:
        perm_importance = pd.DataFrame(
            columns=[
                "variavel",
                "permutation_importance_mean_neg_rmse",
                "permutation_importance_std_neg_rmse",
            ]
        )
        perm_importance.to_csv(output_dir / f"permutation_importance_{args.target}.csv", index=False)

    predicoes = test_df[[args.time_col] + ([args.id_col] if args.id_col in test_df.columns else [])].copy()
    predicoes[f"{args.target}_observado"] = y_test.values
    predicoes[f"{args.target}_predito"] = y_pred_test
    predicoes["erro"] = predicoes[f"{args.target}_observado"] - predicoes[f"{args.target}_predito"]
    predicoes["erro_abs"] = predicoes["erro"].abs()
    predicoes.to_excel(output_dir / f"predicoes_random_forest_{args.target}.xlsx", index=False)

    joblib.dump(best_model, output_dir / f"modelo_random_forest_{args.target}.joblib")

    print("\nRandom Forest concluído com sucesso.")
    print(f"Target: {args.target}")
    print(f"Observações: treino={len(X_train)}, teste={len(X_test)}")
    print(f"RMSE teste: {rmse_test:.8f}")
    print(f"MAE teste: {mae_test:.8f}")
    print(f"R² teste: {r2_test:.8f}")
    print(f"Arquivos salvos em: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
