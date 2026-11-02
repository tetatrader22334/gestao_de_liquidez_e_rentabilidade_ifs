"""
SHAP para modelo Random Forest salvo em .joblib

Arquivos esperados no mesmo diretório, por padrão:
- modelo_random_forest.joblib
- base_final.xlsx

Exemplo de execução:
python 20_shap_random_forest.py --model "outputs/modelos/AM1 - Random forest/geral/rf_geral_roa/modelo_random_forest_ROA.joblib" --data bases/base_final_winsorizada.xlsx --target ROA --output_dir outputs/SHAP/RF/geral/ROA
python 20_shap_random_forest.py --model "outputs/modelos/AM1 - Random forest/geral/rf_geral_roe/modelo_random_forest_ROE.joblib" --data bases/base_final_winsorizada.xlsx --target ROE --output_dir outputs/SHAP/RF/geral/ROE
python 20_shap_random_forest.py --model "outputs/modelos/AM1 - Random forest/geral/rf_geral_nim/modelo_random_forest_NIM.joblib" --data bases/base_final_winsorizada.xlsx --target NIM --output_dir outputs/SHAP/RF/geral/NIM

Saídas:
- shap_importance.csv
- shap_values.csv
- predictions.csv
- shap_summary_beeswarm.png
- shap_importance_bar.png
- shap_waterfall_primeira_observacao.png
- shap_dependence_<variavel>.png para as 5 variáveis mais importantes
"""

from __future__ import annotations

import argparse
import os
import re
import warnings
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap



def patch_sklearn_compatibility(estimator) -> None:
    """
    Corrige incompatibilidades leves de objetos .joblib salvos em uma versão do
    scikit-learn e carregados em outra. No modelo anexado, SimpleImputer salvo
    no scikit-learn 1.7.2 pode não conter o atributo _fill_dtype exigido em 1.8.0.
    """
    visited = set()

    def walk(obj):
        oid = id(obj)
        if oid in visited:
            return
        visited.add(oid)

        if obj.__class__.__name__ == "SimpleImputer":
            if not hasattr(obj, "_fill_dtype") and hasattr(obj, "_fit_dtype"):
                obj._fill_dtype = obj._fit_dtype

        # Pipeline: steps = [(name, estimator), ...]
        if hasattr(obj, "steps"):
            for _, step in obj.steps:
                walk(step)

        # ColumnTransformer: transformers_ after fit, transformers before fit.
        for attr in ["transformers_", "transformers"]:
            if hasattr(obj, attr):
                try:
                    for item in getattr(obj, attr):
                        if len(item) >= 2:
                            walk(item[1])
                except Exception:
                    pass

        # Generic nested estimators.
        if hasattr(obj, "get_params"):
            try:
                for value in obj.get_params(deep=False).values():
                    if hasattr(value, "get_params") or hasattr(value, "steps"):
                        walk(value)
            except Exception:
                pass

    walk(estimator)


def read_table(path: str | Path) -> pd.DataFrame:
    """Lê base tabular em XLSX/XLS/CSV."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    suffix = path.suffix.lower()
    if suffix in [".xlsx", ".xls"]:
        return pd.read_excel(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError("Formato de base não suportado. Use .xlsx, .xls ou .csv.")


def safe_filename(name: str) -> str:
    """Converte nome de variável em nome seguro para arquivo."""
    return re.sub(r"[^A-Za-z0-9_\-.]+", "_", str(name))[:120]


def get_model_features(model, df: pd.DataFrame) -> list[str]:
    """Obtém a lista de variáveis esperadas pelo modelo."""
    if hasattr(model, "feature_names_in_"):
        features = list(model.feature_names_in_)
    elif hasattr(model, "named_steps") and hasattr(model.named_steps.get("model"), "feature_names_in_"):
        features = list(model.named_steps["model"].feature_names_in_)
    else:
        raise ValueError(
            "Não foi possível recuperar feature_names_in_ do modelo. "
            "Nesse caso, informe manualmente a lista de variáveis usada no treino."
        )

    missing = [c for c in features if c not in df.columns]
    if missing:
        raise ValueError(
            "A base não contém todas as variáveis esperadas pelo modelo. "
            f"Variáveis ausentes: {missing}"
        )

    return features


def prepare_tree_model_and_matrix(model, X_raw: pd.DataFrame):
    """
    Se o objeto for um Pipeline preprocess + model, aplica o pré-processamento
    e retorna o estimador final com a matriz transformada.

    Para o arquivo modelo_random_forest_ROA.joblib, o objeto é:
    Pipeline(preprocess=ColumnTransformer, model=RandomForestRegressor).
    """
    if hasattr(model, "named_steps") and "preprocess" in model.named_steps and "model" in model.named_steps:
        preprocess = model.named_steps["preprocess"]
        final_model = model.named_steps["model"]

        X_transformed = preprocess.transform(X_raw)
        if hasattr(X_transformed, "toarray"):
            X_transformed = X_transformed.toarray()

        try:
            transformed_names = list(preprocess.get_feature_names_out())
        except Exception:
            transformed_names = list(X_raw.columns)

        X_model = pd.DataFrame(X_transformed, columns=transformed_names, index=X_raw.index)
        return final_model, X_model

    return model, X_raw


def compute_shap_values(estimator, X_model: pd.DataFrame):
    """Calcula SHAP, priorizando TreeExplainer para modelos de árvore."""
    estimator_name = estimator.__class__.__name__.lower()
    tree_like = any(token in estimator_name for token in ["forest", "tree", "xgb", "lgbm", "catboost"])

    if tree_like:
        explainer = shap.TreeExplainer(estimator)
        shap_values = explainer.shap_values(X_model)
        base_value = explainer.expected_value
    else:
        explainer = shap.Explainer(estimator.predict, X_model)
        explanation = explainer(X_model)
        shap_values = explanation.values
        base_value = explanation.base_values

    # Normaliza casos multiclasse/multioutput.
    if isinstance(shap_values, list):
        # Para regressão simples isso não ocorre. Para múltiplas saídas, usa a primeira.
        shap_values = shap_values[0]

    shap_values = np.asarray(shap_values)
    if shap_values.ndim == 3:
        # Mantém a primeira saída/classe caso haja dimensão adicional.
        shap_values = shap_values[:, :, 0]

    return explainer, shap_values, base_value


def main():
    parser = argparse.ArgumentParser(description="Calcula SHAP para o modelo Random Forest ROA em .joblib.")
    parser.add_argument("--model", default="modelo_random_forest_ROA.joblib", help="Caminho do arquivo .joblib")
    parser.add_argument("--data", default="base_final.xlsx", help="Caminho da base .xlsx, .xls ou .csv")
    parser.add_argument("--target", default="ROA", help="Nome da variável dependente, se existir na base")
    parser.add_argument("--output_dir", default="shap_ROA_outputs", help="Pasta onde os resultados serão salvos")
    parser.add_argument("--max_samples", type=int, default=0, help="Número máximo de linhas para SHAP. Use 0 para usar toda a base")
    parser.add_argument("--random_state", type=int, default=42, help="Semente da amostra")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Carregando modelo...")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model = joblib.load(args.model)
        patch_sklearn_compatibility(model)
        version_warnings = [str(w.message) for w in caught if "InconsistentVersionWarning" in str(w.message)]

    if version_warnings:
        print("AVISO: o modelo foi salvo em versão diferente do scikit-learn instalada neste ambiente.")
        print("Recomendação: execute o script no mesmo ambiente/versão usados no treinamento sempre que possível.")

    print("Carregando base...")
    df = read_table(args.data)

    features = get_model_features(model, df)
    X_raw = df[features].copy()
    y = df[args.target].copy() if args.target and args.target in df.columns else None

    if args.max_samples and args.max_samples > 0 and len(X_raw) > args.max_samples:
        X_raw = X_raw.sample(args.max_samples, random_state=args.random_state)
        if y is not None:
            y = y.loc[X_raw.index]

    print(f"Linhas usadas no SHAP: {len(X_raw)}")
    print(f"Variáveis usadas pelo modelo: {len(features)}")

    estimator, X_model = prepare_tree_model_and_matrix(model, X_raw)

    print(f"Estimador explicado: {estimator.__class__.__name__}")
    print("Calculando valores SHAP...")
    explainer, shap_values, base_value = compute_shap_values(estimator, X_model)

    print("Salvando tabelas...")
    shap_df = pd.DataFrame(shap_values, columns=X_model.columns, index=X_model.index)
    shap_df.to_csv(output_dir / "shap_values.csv", index_label="linha_original")

    importance = (
        pd.DataFrame({
            "variavel": X_model.columns,
            "shap_abs_medio": np.abs(shap_values).mean(axis=0),
            "shap_medio": shap_values.mean(axis=0),
        })
        .sort_values("shap_abs_medio", ascending=False)
        .reset_index(drop=True)
    )
    importance.to_csv(output_dir / "shap_importance.csv", index=False)

    pred = model.predict(X_raw)
    pred_df = pd.DataFrame({"linha_original": X_raw.index, "ROA_predito": pred})
    if y is not None:
        pred_df["ROA_observado"] = y.values
        pred_df["erro"] = pred_df["ROA_observado"] - pred_df["ROA_predito"]
    pred_df.to_csv(output_dir / "predictions.csv", index=False)

    print("Gerando gráficos...")
    plt.figure()
    shap.summary_plot(shap_values, X_model, show=False, max_display=25)
    plt.tight_layout()
    plt.savefig(output_dir / "shap_summary_beeswarm.png", dpi=300, bbox_inches="tight")
    plt.close()

    plt.figure()
    shap.summary_plot(shap_values, X_model, plot_type="bar", show=False, max_display=25)
    plt.tight_layout()
    plt.savefig(output_dir / "shap_importance_bar.png", dpi=300, bbox_inches="tight")
    plt.close()

    # Waterfall da primeira observação.
    try:
        if np.ndim(base_value) > 0:
            base_for_plot = np.asarray(base_value).ravel()[0]
        else:
            base_for_plot = base_value

        explanation_first = shap.Explanation(
            values=shap_values[0],
            base_values=base_for_plot,
            data=X_model.iloc[0].values,
            feature_names=list(X_model.columns),
        )
        shap.plots.waterfall(explanation_first, max_display=20, show=False)
        plt.tight_layout()
        plt.savefig(output_dir / "shap_waterfall_primeira_observacao.png", dpi=300, bbox_inches="tight")
        plt.close()
    except Exception as exc:
        print(f"Não foi possível gerar o waterfall plot: {exc}")

    # Dependence plots das 5 variáveis mais importantes.
    top_features = importance["variavel"].head(5).tolist()
    for feature in top_features:
        try:
            shap.dependence_plot(feature, shap_values, X_model, show=False)
            plt.tight_layout()
            plt.savefig(output_dir / f"shap_dependence_{safe_filename(feature)}.png", dpi=300, bbox_inches="tight")
            plt.close()
        except Exception as exc:
            print(f"Não foi possível gerar dependence plot para {feature}: {exc}")

    print("Concluído.")
    print(f"Resultados salvos em: {output_dir.resolve()}")
    print("Top 10 variáveis por |SHAP| médio:")
    print(importance.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
