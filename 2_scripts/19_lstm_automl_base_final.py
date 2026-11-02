#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
lstm_automl_base_final.py

Treina um modelo LSTM para dados em painel temporal de instituições financeiras,
com otimização automática de hiperparâmetros via Optuna (AutoML).

python 19_lstm_automl_base_final.py --input bases/base_final_winsorizada.xlsx --output_dir "outputs/modelos/AM2 - LSTM/geral" --target ROA --feature_preset "compact_banking" --n_trials 50 --horizon 1
python 19_lstm_automl_base_final.py --input bases/base_final_winsorizada.xlsx --output_dir "outputs/modelos/AM2 - LSTM/geral" --target ROE --feature_preset "compact_banking" --n_trials 50 --horizon 1
python 19_lstm_automl_base_final.py --input bases/base_final_winsorizada.xlsx --output_dir "outputs/modelos/AM2 - LSTM/geral" --target NIM --feature_preset "compact_banking" --n_trials 50 --horizon 1

Dependências:
    pip install pandas openpyxl numpy scikit-learn tensorflow optuna joblib matplotlib

Notas metodológicas para a dissertação:
- A LSTM é adequada para estruturas sequenciais por possuir mecanismos de memória que mitigam
  problemas de dependências temporais longas em redes recorrentes (Hochreiter; Schmidhuber, 1997).
- A otimização automática usa Optuna, framework de hyperparameter optimization com API define-by-run,
  amostragem adaptativa e pruning de tentativas pouco promissoras (Akiba et al., 2019).
- O script faz divisão temporal por período previsto, ajusta imputador/escalonador somente no treino e 
  avalia o desempenho fora da amostra, reduzindo risco de data leakage.

Referências em formato ABNT:
HOCHREITER, Sepp; SCHMIDHUBER, Jürgen. Long short-term memory. Neural Computation, v. 9,
n. 8, p. 1735-1780, 1997.

AKIBA, Takuya et al. Optuna: a next-generation hyperparameter optimization framework. In:
PROCEEDINGS OF THE 25TH ACM SIGKDD INTERNATIONAL CONFERENCE ON KNOWLEDGE DISCOVERY
& DATA MINING, 2019. Proceedings [...]. New York: ACM, 2019. p. 2623-2631.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import warnings
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

warnings.filterwarnings("ignore")

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import RobustScaler, StandardScaler

try:
    import optuna
except ImportError as exc:
    raise SystemExit(
        "Optuna não está instalado. Instale com: pip install optuna"
    ) from exc

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers, regularizers
except ImportError as exc:
    raise SystemExit(
        "TensorFlow não está instalado. Instale com: pip install tensorflow"
    ) from exc


def set_reproducibility(seed: int) -> None:
    """Configura sementes para maior reprodutibilidade."""
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    tf.keras.utils.set_random_seed(seed)
    try:
        tf.config.experimental.enable_op_determinism()
    except Exception:
        pass


@dataclass
class SplitInfo:
    train_periods: List
    val_periods: List
    test_periods: List
    n_train: int
    n_val: int
    n_test: int


class OptunaPruningCallback(keras.callbacks.Callback):
    """Callback simples para reportar val_loss ao Optuna e interromper trials ruins."""

    def __init__(self, trial: optuna.Trial, monitor: str = "val_loss") -> None:
        super().__init__()
        self.trial = trial
        self.monitor = monitor

    def on_epoch_end(self, epoch: int, logs: Dict | None = None) -> None:
        logs = logs or {}
        value = logs.get(self.monitor)
        if value is None:
            return
        self.trial.report(float(value), step=epoch)
        if self.trial.should_prune():
            raise optuna.TrialPruned(f"Trial podado no epoch {epoch} com {self.monitor}={value:.6f}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Treina LSTM com AutoML/Optuna para base financeira em painel temporal."
    )
    parser.add_argument("--input", required=True, help="Caminho do arquivo .xlsx ou .csv de entrada.")
    parser.add_argument("--sheet", default=0, help="Aba do Excel. Use nome ou índice. Default: 0.")
    parser.add_argument("--target", default="ROA", help="Variável dependente: ROA, ROE, NIM ou outra coluna numérica.")
    parser.add_argument("--entity_col", default="id_entidade", help="Coluna identificadora da instituição.")
    parser.add_argument("--time_col", default="AnoMes_ord", help="Coluna temporal usada para ordenação e split.")
    parser.add_argument("--horizon", type=int, default=1, help="Horizonte de previsão em períodos. 1 = próximo trimestre.")
    parser.add_argument("--n_trials", type=int, default=50, help="Número de tentativas de AutoML/Optuna.")
    parser.add_argument("--max_epochs", type=int, default=200, help="Máximo de epochs por trial.")
    parser.add_argument("--patience", type=int, default=20, help="Paciência do early stopping.")
    parser.add_argument("--val_periods", type=int, default=8, help="Número de períodos finais antes do teste para validação.")
    parser.add_argument("--test_periods", type=int, default=8, help="Número de períodos finais para teste.")
    parser.add_argument("--output_dir", default="outputs_lstm_automl", help="Diretório de saída.")
    parser.add_argument("--seed", type=int, default=42, help="Semente aleatória.")
    parser.add_argument(
        "--feature_preset",
        choices=["all_numeric", "compact_banking", "no_raw_amounts"],
        default="no_raw_amounts",
        help=(
            "Conjunto de variáveis explicativas. "
            "all_numeric usa todas as numéricas elegíveis; "
            "compact_banking prioriza liquidez, capital, macro, tamanho, mercado e razões; "
            "no_raw_amounts remove níveis contábeis brutos e mantém logs/razões/indicadores."
        ),
    )
    parser.add_argument(
        "--include_profitability_history",
        action="store_true",
        help="Inclui ROA/ROE/NIM históricos nas sequências. Por padrão, remove todos para evitar tautologia.",
    )
    parser.add_argument(
        "--include_entity_dummies",
        action="store_true",
        help="Inclui dummies de instituição como variáveis estáticas repetidas no tempo.",
    )
    parser.add_argument(
        "--sequence_grid",
        default="4,6,8,12",
        help="Tamanhos de sequência que o Optuna poderá escolher. Ex.: '4,8,12'.",
    )
    return parser.parse_args()


def load_table(path: str, sheet=0) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {p}")
    if p.suffix.lower() in [".xlsx", ".xls", ".xlsm"]:
        # argparse recebe sheet como string; converte para inteiro quando aplicável.
        try:
            sheet_arg = int(sheet)
        except (TypeError, ValueError):
            sheet_arg = sheet
        df = pd.read_excel(p, sheet_name=sheet_arg)
    elif p.suffix.lower() in [".csv", ".txt"]:
        df = pd.read_csv(p)
    else:
        raise ValueError("Formato não suportado. Use .xlsx, .xls, .xlsm ou .csv.")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def choose_features(
    df: pd.DataFrame,
    target: str,
    entity_col: str,
    time_col: str,
    preset: str,
    include_profitability_history: bool,
    include_entity_dummies: bool,
) -> Tuple[pd.DataFrame, List[str]]:
    if target not in df.columns:
        raise ValueError(f"Target '{target}' não encontrado. Colunas disponíveis: {list(df.columns)}")
    if entity_col not in df.columns:
        raise ValueError(f"entity_col '{entity_col}' não encontrada.")
    if time_col not in df.columns:
        raise ValueError(f"time_col '{time_col}' não encontrada.")

    out = df.copy()

    # Converte colunas numéricas quando possível, preservando identificadores.
    for col in out.columns:
        if col not in [entity_col]:
            out[col] = pd.to_numeric(out[col], errors="ignore")

    profitability_cols = [c for c in ["ROA", "ROE", "NIM"] if c in out.columns]
    base_drop = {entity_col, target}

    # A coluna temporal é usada para ordenação/split. Evitamos usá-la diretamente como regressor
    # para reduzir o risco de o modelo aprender apenas tendência temporal mecânica.
    base_drop.add(time_col)

    if not include_profitability_history:
        base_drop.update(profitability_cols)
    else:
        # Mesmo com histórico, a variável alvo contemporânea no y não aparece no X de t+horizon;
        # ela aparecerá apenas nos lags da janela. Mantemos as outras dependentes como histórico.
        base_drop.discard(target)

    numeric_cols = [c for c in out.columns if pd.api.types.is_numeric_dtype(out[c]) and c not in base_drop]

    raw_amount_keywords = [
        "ativo_total", "disponibilidades", "permanente_ajustado", "patrimonio_liquido",
        "passivo_total", "lucro_liquido", "captacoes", "depositos", "despesas_",
        "operacoes_de_credito", "provisao_sobre", "receitas_", "rendas_", "resultado_",
        "ativos_totais_banco_brl", 
    ]

    if preset == "compact_banking":
        keep_patterns = [
            # "lcr", "nsfr", "basileia", "imobilizacao", "ipca", "selic", "pib",
            # "market_share", "hhi", "_log", "sobre_", "ativo_total", "estatal",
            # "controle_estrangeiro", "crise", "flag_outlier", "trimestre",
            
"patrimonio_liquido_log","operacoes_de_credito_sobre_captacoes","resultado_de_provisao_pcddl_sobre_ativo_total","resultado_de_intermediacao_financeira","captacoes_sobre_ativo_total","rendas_de_prestacao_de_servicos_sobre_ativo_total","despesas_tributarias_sobre_receitas","rendas_de_operacoes_com_TVM_sobre_ativo_total","despesas_adm_sobre_receitas","hhi_periodo_dec","liquidez_imediata","selic_fim_trimestre_dec","despesas_de_intermediacao_sobre_receitas","rendas_de_tarifas_bancarias_sobre_ativo_total","despesas_de_captacao_sobre_receitas","ativos_sobre_depositos","disponibilidades_sobre_depositos","indice_de_basileia_dec","ipca_fim_trimestre_dec","multiplicador_capital_proprio","pib_indice_sa_log","receitas_de_intermediacao_financeira_sobre_ativo_total","estatal","controle_estrangeiro","crise_nme","crise_covid"
        ]
        features = [c for c in numeric_cols if any(pat in c for pat in keep_patterns)]
    elif preset == "no_raw_amounts":
        features = []
        for c in numeric_cols:
            is_raw = any(k in c for k in raw_amount_keywords)
            is_transformed = c.endswith("_log") or "sobre_" in c or c.endswith("_dec")
            is_control = c in ["trimestre", "estatal", "controle_estrangeiro", "crise_nme", "crise_covid"]
            is_market_macro_flag = any(k in c for k in ["ipca", "selic", "pib", "market_share", "hhi", "flag_outlier"])
            if (not is_raw) or is_transformed or is_control or is_market_macro_flag:
                features.append(c)
    else:
        features = numeric_cols

    # Remove duplicidades preservando ordem.
    features = list(dict.fromkeys(features))

    if include_profitability_history:
        for col in profitability_cols:
            if col not in features and col != target and pd.api.types.is_numeric_dtype(out[col]):
                features.append(col)
        # inclui o próprio alvo como lag histórico, se solicitado
        if target not in features:
            features.append(target)

    if include_entity_dummies:
        dummies = pd.get_dummies(out[entity_col].astype(str), prefix="inst", dtype=float)
        out = pd.concat([out, dummies], axis=1)
        features.extend(dummies.columns.tolist())

    # Mantém apenas colunas com alguma variação e valores finitos após troca de inf por NaN.
    out[features] = out[features].replace([np.inf, -np.inf], np.nan)
    valid_features = []
    for c in features:
        series = out[c]
        if series.notna().sum() == 0:
            continue
        if series.nunique(dropna=True) <= 1:
            continue
        valid_features.append(c)

    if not valid_features:
        raise ValueError("Nenhuma variável explicativa válida foi selecionada.")
    return out, valid_features


def make_sequences(
    df: pd.DataFrame,
    features: Sequence[str],
    target: str,
    entity_col: str,
    time_col: str,
    seq_len: int,
    horizon: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Cria janelas por instituição: X[t-seq+1:t] -> y[t+horizon]."""
    if horizon < 0:
        raise ValueError("horizon deve ser >= 0.")

    X_list, y_list, time_list, entity_list = [], [], [], []
    needed = list(features) + [target, entity_col, time_col]
    data = df[needed].copy()
    data[target] = pd.to_numeric(data[target], errors="coerce")
    data = data.dropna(subset=[target, entity_col, time_col])

    for entity, g in data.groupby(entity_col, sort=False):
        g = g.sort_values(time_col).reset_index(drop=True)
        values = g[list(features)].to_numpy(dtype=float)
        y_values = g[target].to_numpy(dtype=float)
        times = g[time_col].to_numpy()

        last_start = len(g) - horizon
        for end_idx in range(seq_len - 1, last_start):
            y_idx = end_idx + horizon
            if y_idx >= len(g):
                continue
            X_window = values[end_idx - seq_len + 1 : end_idx + 1]
            y_value = y_values[y_idx]
            if np.isnan(y_value):
                continue
            X_list.append(X_window)
            y_list.append(y_value)
            time_list.append(times[y_idx])
            entity_list.append(entity)

    if len(X_list) == 0:
        raise ValueError(
            "Nenhuma sequência criada. Reduza seq_len, reduza horizon ou verifique a coluna temporal."
        )

    return (
        np.asarray(X_list, dtype=float),
        np.asarray(y_list, dtype=float),
        np.asarray(time_list),
        np.asarray(entity_list, dtype=object),
    )


def temporal_split(
    y_times: np.ndarray,
    val_periods: int,
    test_periods: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, SplitInfo]:
    unique_times = np.array(sorted(pd.unique(y_times)))
    if len(unique_times) <= val_periods + test_periods + 2:
        raise ValueError(
            f"Poucos períodos ({len(unique_times)}) para split com val_periods={val_periods} "
            f"e test_periods={test_periods}. Reduza esses parâmetros."
        )

    test_times = unique_times[-test_periods:]
    val_times = unique_times[-(test_periods + val_periods) : -test_periods]
    train_times = unique_times[: -(test_periods + val_periods)]

    train_mask = np.isin(y_times, train_times)
    val_mask = np.isin(y_times, val_times)
    test_mask = np.isin(y_times, test_times)

    info = SplitInfo(
        train_periods=train_times.tolist(),
        val_periods=val_times.tolist(),
        test_periods=test_times.tolist(),
        n_train=int(train_mask.sum()),
        n_val=int(val_mask.sum()),
        n_test=int(test_mask.sum()),
    )
    return train_mask, val_mask, test_mask, info


def make_scaler(name: str):
    if name == "standard":
        return StandardScaler()
    if name == "robust":
        return RobustScaler(quantile_range=(25.0, 75.0))
    raise ValueError(f"Scaler inválido: {name}")


def fit_transform_sequences(
    X_train: np.ndarray,
    X_val: np.ndarray,
    X_test: np.ndarray,
    scaler_name: str,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, SimpleImputer, object]:
    n_features = X_train.shape[-1]
    imputer = SimpleImputer(strategy="median")
    scaler = make_scaler(scaler_name)

    train_2d = X_train.reshape(-1, n_features)
    imputer.fit(train_2d)
    scaler.fit(imputer.transform(train_2d))

    def transform(X: np.ndarray) -> np.ndarray:
        shape = X.shape
        X2 = X.reshape(-1, n_features)
        X2 = imputer.transform(X2)
        X2 = scaler.transform(X2)
        return X2.reshape(shape)

    return transform(X_train), transform(X_val), transform(X_test), imputer, scaler


def scale_y(y_train: np.ndarray, y_val: np.ndarray, y_test: np.ndarray):
    scaler = StandardScaler()
    scaler.fit(y_train.reshape(-1, 1))
    return (
        scaler.transform(y_train.reshape(-1, 1)).ravel(),
        scaler.transform(y_val.reshape(-1, 1)).ravel(),
        scaler.transform(y_test.reshape(-1, 1)).ravel(),
        scaler,
    )


def build_lstm_model(
    input_shape: Tuple[int, int],
    params: Dict,
) -> keras.Model:
    model = keras.Sequential(name="lstm_automl_panel")
    model.add(layers.Input(shape=input_shape))

    l2_value = params.get("l2", 0.0)
    reg = regularizers.l2(l2_value) if l2_value > 0 else None
    n_layers = int(params["n_layers"])
    units = int(params["units"])
    dropout = float(params["dropout"])
    recurrent_dropout = float(params.get("recurrent_dropout", 0.0))
    bidirectional = bool(params.get("bidirectional", False))

    for i in range(n_layers):
        return_sequences = i < n_layers - 1
        lstm_layer = layers.LSTM(
            units=units,
            return_sequences=return_sequences,
            dropout=dropout,
            recurrent_dropout=recurrent_dropout,
            kernel_regularizer=reg,
        )
        if bidirectional:
            model.add(layers.Bidirectional(lstm_layer))
        else:
            model.add(lstm_layer)
        if params.get("layer_norm", False):
            model.add(layers.LayerNormalization())

    dense_units = int(params.get("dense_units", 0))
    if dense_units > 0:
        model.add(layers.Dense(dense_units, activation="relu", kernel_regularizer=reg))
        model.add(layers.Dropout(dropout))

    model.add(layers.Dense(1, activation="linear"))

    lr = float(params["learning_rate"])
    optimizer_name = params.get("optimizer", "adam")
    if optimizer_name == "rmsprop":
        optimizer = keras.optimizers.RMSprop(learning_rate=lr)
    else:
        optimizer = keras.optimizers.Adam(learning_rate=lr)

    model.compile(optimizer=optimizer, loss="mse", metrics=[keras.metrics.MeanAbsoluteError(name="mae")])
    return model


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred)) if len(np.unique(y_true)) > 1 else float("nan")
    # Acurácia direcional: compara sinal da variação sequencial observada e prevista no conjunto ordenado.
    if len(y_true) > 1:
        dy_true = np.sign(np.diff(y_true))
        dy_pred = np.sign(np.diff(y_pred))
        directional_accuracy = float(np.mean(dy_true == dy_pred))
    else:
        directional_accuracy = float("nan")
    return {"rmse": rmse, "mae": mae, "r2": r2, "directional_accuracy": directional_accuracy}


def save_training_plot(history: keras.callbacks.History, output_path: Path) -> None:
    try:
        import matplotlib.pyplot as plt

        plt.figure(figsize=(8, 5))
        plt.plot(history.history.get("loss", []), label="train_loss")
        plt.plot(history.history.get("val_loss", []), label="val_loss")
        plt.xlabel("Epoch")
        plt.ylabel("MSE escalonado")
        plt.title("Curva de treinamento - LSTM")
        plt.legend()
        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()
    except Exception as exc:
        print(f"Aviso: não foi possível salvar gráfico de treinamento: {exc}")


def main() -> None:
    args = parse_args()
    set_reproducibility(args.seed)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_table(args.input, sheet=args.sheet)
    df, features = choose_features(
        df=df,
        target=args.target,
        entity_col=args.entity_col,
        time_col=args.time_col,
        preset=args.feature_preset,
        include_profitability_history=args.include_profitability_history,
        include_entity_dummies=args.include_entity_dummies,
    )

    sequence_grid = [int(x.strip()) for x in args.sequence_grid.split(",") if x.strip()]
    if min(sequence_grid) < 1:
        raise ValueError("Todos os valores de sequence_grid devem ser >= 1.")

    print("=" * 80)
    print("Base carregada")
    print(f"Linhas: {len(df):,} | Colunas: {df.shape[1]:,}")
    print(f"Instituições: {df[args.entity_col].nunique():,}")
    print(f"Períodos: {df[args.time_col].nunique():,} | {df[args.time_col].min()} a {df[args.time_col].max()}")
    print(f"Target: {args.target} | Horizon: {args.horizon}")
    print(f"Features selecionadas: {len(features)}")
    print("=" * 80)

    def objective(trial: optuna.Trial) -> float:
        tf.keras.backend.clear_session()

        params = {
            "seq_len": trial.suggest_categorical("seq_len", sequence_grid),
            "scaler": trial.suggest_categorical("scaler", ["standard", "robust"]),
            "n_layers": trial.suggest_int("n_layers", 1, 2),
            "units": trial.suggest_categorical("units", [16, 32, 64, 96, 128]),
            "dropout": trial.suggest_float("dropout", 0.0, 0.45, step=0.05),
            "recurrent_dropout": trial.suggest_categorical("recurrent_dropout", [0.0, 0.05, 0.10]),
            "dense_units": trial.suggest_categorical("dense_units", [0, 16, 32, 64]),
            "learning_rate": trial.suggest_float("learning_rate", 1e-4, 5e-3, log=True),
            "l2": trial.suggest_float("l2", 1e-8, 1e-3, log=True),
            "batch_size": trial.suggest_categorical("batch_size", [8, 16, 32, 64]),
            "optimizer": trial.suggest_categorical("optimizer", ["adam", "rmsprop"]),
            "bidirectional": trial.suggest_categorical("bidirectional", [False, True]),
            "layer_norm": trial.suggest_categorical("layer_norm", [False, True]),
        }

        X, y, y_times, _entities = make_sequences(
            df=df,
            features=features,
            target=args.target,
            entity_col=args.entity_col,
            time_col=args.time_col,
            seq_len=params["seq_len"],
            horizon=args.horizon,
        )
        train_mask, val_mask, test_mask, split_info = temporal_split(
            y_times=y_times,
            val_periods=args.val_periods,
            test_periods=args.test_periods,
        )
        if split_info.n_train < 30 or split_info.n_val < 10:
            raise optuna.TrialPruned("Amostra insuficiente no treino/validação para esta configuração.")

        X_train, X_val, X_test = X[train_mask], X[val_mask], X[test_mask]
        y_train, y_val, y_test = y[train_mask], y[val_mask], y[test_mask]

        X_train, X_val, X_test, _imputer, _x_scaler = fit_transform_sequences(
            X_train, X_val, X_test, scaler_name=params["scaler"]
        )
        y_train_s, y_val_s, _y_test_s, y_scaler = scale_y(y_train, y_val, y_test)

        model = build_lstm_model(input_shape=X_train.shape[1:], params=params)
        callbacks = [
            keras.callbacks.EarlyStopping(
                monitor="val_loss", patience=args.patience, mode="min", restore_best_weights=True
            ),
            keras.callbacks.ReduceLROnPlateau(
                monitor="val_loss", patience=max(4, args.patience // 3), factor=0.5, min_lr=1e-6
            ),
            OptunaPruningCallback(trial, monitor="val_loss"),
        ]
        history = model.fit(
            X_train,
            y_train_s,
            validation_data=(X_val, y_val_s),
            epochs=args.max_epochs,
            batch_size=params["batch_size"],
            verbose=0,
            shuffle=False,
            callbacks=callbacks,
        )

        val_pred_s = model.predict(X_val, verbose=0).ravel()
        val_pred = y_scaler.inverse_transform(val_pred_s.reshape(-1, 1)).ravel()
        val_rmse = regression_metrics(y_val, val_pred)["rmse"]
        trial.set_user_attr("best_epoch", int(np.argmin(history.history.get("val_loss", [np.inf])) + 1))
        trial.set_user_attr("n_train", split_info.n_train)
        trial.set_user_attr("n_val", split_info.n_val)
        trial.set_user_attr("n_test", split_info.n_test)
        return val_rmse

    sampler = optuna.samplers.TPESampler(seed=args.seed, multivariate=True, group=True)
    pruner = optuna.pruners.MedianPruner(n_startup_trials=max(5, args.n_trials // 10), n_warmup_steps=10)
    study = optuna.create_study(direction="minimize", sampler=sampler, pruner=pruner)
    study.optimize(objective, n_trials=args.n_trials, show_progress_bar=True)

    best = study.best_trial
    best_params = dict(best.params)
    print("\nMelhor trial:")
    print(f"  Trial: {best.number}")
    print(f"  Val RMSE: {best.value:.8f}")
    print(f"  Params: {json.dumps(best_params, indent=2, ensure_ascii=False)}")

    # Treinamento final com os melhores hiperparâmetros e avaliação no teste temporal.
    tf.keras.backend.clear_session()
    seq_len = int(best_params["seq_len"])
    X, y, y_times, entities = make_sequences(
        df=df,
        features=features,
        target=args.target,
        entity_col=args.entity_col,
        time_col=args.time_col,
        seq_len=seq_len,
        horizon=args.horizon,
    )
    train_mask, val_mask, test_mask, split_info = temporal_split(
        y_times=y_times,
        val_periods=args.val_periods,
        test_periods=args.test_periods,
    )

    X_train_raw, X_val_raw, X_test_raw = X[train_mask], X[val_mask], X[test_mask]
    y_train, y_val, y_test = y[train_mask], y[val_mask], y[test_mask]
    time_train, time_val, time_test = y_times[train_mask], y_times[val_mask], y_times[test_mask]
    ent_train, ent_val, ent_test = entities[train_mask], entities[val_mask], entities[test_mask]

    X_train, X_val, X_test, imputer, x_scaler = fit_transform_sequences(
        X_train_raw, X_val_raw, X_test_raw, scaler_name=best_params["scaler"]
    )
    y_train_s, y_val_s, y_test_s, y_scaler = scale_y(y_train, y_val, y_test)

    model = build_lstm_model(input_shape=X_train.shape[1:], params=best_params)
    final_callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=args.patience, mode="min", restore_best_weights=True
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", patience=max(4, args.patience // 3), factor=0.5, min_lr=1e-6
        ),
    ]
    history = model.fit(
        X_train,
        y_train_s,
        validation_data=(X_val, y_val_s),
        epochs=args.max_epochs,
        batch_size=int(best_params["batch_size"]),
        verbose=1,
        shuffle=False,
        callbacks=final_callbacks,
    )

    pred_train = y_scaler.inverse_transform(model.predict(X_train, verbose=0).reshape(-1, 1)).ravel()
    pred_val = y_scaler.inverse_transform(model.predict(X_val, verbose=0).reshape(-1, 1)).ravel()
    pred_test = y_scaler.inverse_transform(model.predict(X_test, verbose=0).reshape(-1, 1)).ravel()

    metrics = {
        "target": args.target,
        "horizon": args.horizon,
        "feature_preset": args.feature_preset,
        "include_profitability_history": args.include_profitability_history,
        "include_entity_dummies": args.include_entity_dummies,
        "n_features": len(features),
        "features": features,
        "split_info": asdict(split_info),
        "best_trial_number": int(best.number),
        "best_validation_rmse_from_study": float(best.value),
        "best_params": best_params,
        "train_metrics": regression_metrics(y_train, pred_train),
        "validation_metrics": regression_metrics(y_val, pred_val),
        "test_metrics": regression_metrics(y_test, pred_test),
    }

    predictions = pd.DataFrame(
        {
            args.entity_col: np.concatenate([ent_train, ent_val, ent_test]),
            args.time_col: np.concatenate([time_train, time_val, time_test]),
            "split": (["train"] * len(y_train)) + (["validation"] * len(y_val)) + (["test"] * len(y_test)),
            f"{args.target}_real": np.concatenate([y_train, y_val, y_test]),
            f"{args.target}_previsto": np.concatenate([pred_train, pred_val, pred_test]),
        }
    )
    predictions["erro"] = predictions[f"{args.target}_real"] - predictions[f"{args.target}_previsto"]
    predictions["erro_abs"] = predictions["erro"].abs()

    # Artefatos de saída.
    model_path = output_dir / f"lstm_automl_{args.target}.keras"
    model.save(model_path)
    joblib.dump(
        {
            "imputer": imputer,
            "x_scaler": x_scaler,
            "y_scaler": y_scaler,
            "features": features,
            "args": vars(args),
            "best_params": best_params,
        },
        output_dir / f"preprocessadores_{args.target}.joblib",
    )
    predictions.sort_values(["split", args.entity_col, args.time_col]).to_csv(
        output_dir / f"predicoes_{args.target}.csv", index=False, encoding="utf-8-sig"
    )
    with open(output_dir / f"metricas_{args.target}.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2, default=str)

    trials_df = study.trials_dataframe(attrs=("number", "value", "params", "state", "user_attrs"))
    trials_df.to_csv(output_dir / f"optuna_trials_{args.target}.csv", index=False, encoding="utf-8-sig")
    joblib.dump(study, output_dir / f"optuna_study_{args.target}.joblib")
    save_training_plot(history, output_dir / f"curva_treinamento_{args.target}.png")

    print("\nMétricas finais:")
    print(json.dumps({k: metrics[k] for k in ["train_metrics", "validation_metrics", "test_metrics"]}, indent=2))
    print("\nArquivos salvos em:")
    print(f"  {output_dir.resolve()}")
    print("\nPrincipais arquivos:")
    print(f"  Modelo Keras: {model_path}")
    print(f"  Métricas: {output_dir / f'metricas_{args.target}.json'}")
    print(f"  Predições: {output_dir / f'predicoes_{args.target}.csv'}")
    print(f"  Trials Optuna: {output_dir / f'optuna_trials_{args.target}.csv'}")


if __name__ == "__main__":
    main()
