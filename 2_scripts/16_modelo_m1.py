#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
O script:
- lê .xlsx/.xls/.csv/.parquet;
- permite escolher a aba da planilha com --sheet;
- reconhece id_entidade como identificador de painel;
- reconhece AnoMes_ord como coluna temporal;
- cria ROA e NIM quando essas variáveis não existem na base;
- tenta criar ROE apenas se houver coluna de patrimônio líquido/equity disponível;
- usa, por padrão, um conjunto de regressores compatível com M1, evitando usar
  automaticamente todas as contas contábeis brutas como variáveis explicativas;
- executa VIF, White, Breusch-Pagan, Chow/Poolability, Hausman e BP-LM para RE;
- estima modelos pooled OLS, efeitos fixos por LSDV, efeitos aleatórios por MixedLM
  e um modelo misto explícito com efeitos fixos dos regressores e intercepto aleatório
  por instituição;
- adiciona erros-padrão robustos clusterizados por instituição para pooled OLS e
  efeitos fixos por LSDV.

python 16_modelo_m1.py --input bases/base_final.xlsx --sheet base --output-xlsx "outputs/modelos/M1 - Painel estático/geral/geral_roa.xlsx" --output-txt "outputs/modelos/M1 - Painel estático/geral/geral_roa.txt" --x-vars "patrimonio_liquido_log, operacoes_de_credito_sobre_captacoes, resultado_de_provisao_pcddl_sobre_ativo_total, resultado_de_intermediacao_financeira, captacoes_sobre_ativo_total, rendas_de_prestacao_de_servicos_sobre_ativo_total, despesas_tributarias_sobre_receitas, rendas_de_operacoes_com_TVM_sobre_ativo_total, despesas_adm_sobre_receitas, hhi_periodo_dec, liquidez_imediata, controle_estrangeiro, selic_fim_trimestre_dec, despesas_de_intermediacao_sobre_receitas, rendas_de_tarifas_bancarias_sobre_ativo_total, despesas_de_captacao_sobre_receitas, crise_covid, ativos_sobre_depositos, crise_nme, disponibilidades_sobre_depositos, indice_de_basileia_dec, ipca_fim_trimestre_dec, multiplicador_capital_proprio, pib_indice_sa_log, receitas_de_intermediacao_financeira_sobre_ativo_total" --dep-vars ROA
python 16_modelo_m1.py --input bases/base_final.xlsx --sheet base --output-xlsx "outputs/modelos/M1 - Painel estático/geral/geral_roe.xlsx" --output-txt "outputs/modelos/M1 - Painel estático/geral/geral_roe.txt" --x-vars "patrimonio_liquido_log, operacoes_de_credito_sobre_captacoes, resultado_de_provisao_pcddl_sobre_ativo_total, resultado_de_intermediacao_financeira, captacoes_sobre_ativo_total, rendas_de_prestacao_de_servicos_sobre_ativo_total, despesas_tributarias_sobre_receitas, rendas_de_operacoes_com_TVM_sobre_ativo_total, despesas_adm_sobre_receitas, hhi_periodo_dec, liquidez_imediata, controle_estrangeiro, selic_fim_trimestre_dec, despesas_de_intermediacao_sobre_receitas, rendas_de_tarifas_bancarias_sobre_ativo_total, despesas_de_captacao_sobre_receitas, crise_covid, ativos_sobre_depositos, crise_nme, disponibilidades_sobre_depositos, indice_de_basileia_dec, ipca_fim_trimestre_dec, multiplicador_capital_proprio, pib_indice_sa_log, receitas_de_intermediacao_financeira_sobre_ativo_total" --dep-vars ROE
python 16_modelo_m1.py --input bases/base_final.xlsx --sheet base --output-xlsx "outputs/modelos/M1 - Painel estático/geral/geral_nim.xlsx" --output-txt "outputs/modelos/M1 - Painel estático/geral/geral_nim.txt" --x-vars "patrimonio_liquido_log, operacoes_de_credito_sobre_captacoes, resultado_de_provisao_pcddl_sobre_ativo_total, resultado_de_intermediacao_financeira, captacoes_sobre_ativo_total, rendas_de_prestacao_de_servicos_sobre_ativo_total, despesas_tributarias_sobre_receitas, rendas_de_operacoes_com_TVM_sobre_ativo_total, despesas_adm_sobre_receitas, hhi_periodo_dec, liquidez_imediata, controle_estrangeiro, selic_fim_trimestre_dec, despesas_de_intermediacao_sobre_receitas, rendas_de_tarifas_bancarias_sobre_ativo_total, despesas_de_captacao_sobre_receitas, crise_covid, ativos_sobre_depositos, crise_nme, disponibilidades_sobre_depositos, indice_de_basileia_dec, ipca_fim_trimestre_dec, multiplicador_capital_proprio, pib_indice_sa_log, receitas_de_intermediacao_financeira_sobre_ativo_total" --dep-vars NIM

Observações metodológicas:
1) O teste LM de Breusch-Pagan para efeitos aleatórios é implementado na forma
   clássica para painel balanceado. Para painel desbalanceado, reporta-se uma
   aproximação com T médio.
2) A estimação de efeitos aleatórios usa MixedLM com intercepto aleatório por
   entidade. Em bases com forte colinearidade, essa etapa pode falhar; nesses
   casos, o erro é registrado na aba correspondente.
3) O modelo misto é estimado por MixedLM: os coeficientes dos regressores são
   tratados como efeitos fixos e o intercepto por instituição como efeito aleatório.
   Opcionalmente, --mixed-random-slopes permite informar regressores com inclinação
   aleatória por instituição, mas recomenda-se parcimônia em painéis pequenos.
4) Os erros-padrão robustos clusterizados são calculados para os modelos OLS
   estimados por statsmodels, isto é, pooled OLS e FE/LSDV. Para MixedLM, o script
   reporta os erros-padrão do ajuste ML/REML; statsmodels não oferece, de forma
   estável, covariância cluster robusta para MixedLM.
5) O conjunto padrão de regressores M1 pode ser alterado com --x-vars.
6) Por padrão, a amostra é de casos completos para y e X. Use --impute-x median
   apenas se desejar imputar os regressores pela mediana, mantendo y sem imputação.
"""

from __future__ import annotations

import argparse
import re
import warnings
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.regression.mixed_linear_model import MixedLM
from statsmodels.stats.diagnostic import het_breuschpagan, het_white
from statsmodels.stats.outliers_influence import variance_inflation_factor


# Identificadores compatíveis com bases antigas e com a base_un_ajustada.
ID_CANDIDATES = [
    "id_entidade", "Ticker", "ticker", "CodInst", "codInst", "cod_inst", "Empresa", "empresa",
    "Nome", "nome"
]

TIME_CANDIDATES = [
    "AnoMes_ord", "AnoMes", "ano_mes", "DataRef", "data_ref", "data", "Data"
]

DEPENDENT_CANDIDATES = ["ROA", "ROE", "NIM"]

# Regressores padrão para a base_un_ajustada/M1.
# O objetivo é evitar usar, por padrão, todas as contas contábeis brutas como X,
# pois isso pode gerar leakage e amostras vazias por missing em massa.
DEFAULT_M1_REGRESSORS = [
    # Liquidez
    "lcr_dec",
    "nsfr_dec",

    # Capital, alavancagem e imobilização

    # Porte
 
    # Despesas
    
    # Receitas
    
    # Resultado
    
    # Concentração

    # Macroeconômicas

    # Dummies institucionais e de crise
    "estatal",
    "controle_estrangeiro",
    "crise_nme",
    "crise_covid",
]

# Colunas que não devem entrar automaticamente como regressores no modo all_numeric.
EXCLUDE_AS_X_BASE = set(ID_CANDIDATES + TIME_CANDIDATES + DEPENDENT_CANDIDATES + [
    "trimestre",
])

# Componentes usados para construir dependentes; também são removidos no modo all_numeric
# para reduzir risco de leakage mecânico.
DEPENDENT_COMPONENTS = {
    "is_netIncomeFromContinuingOps",
    "is_incomeBeforeTax",
    "is_netIncomeBeforeTaxes",
    "resultado_de_intermediacao_financeira",
    "receitas_de_intermediacao_financeira",
    "despesas_de_intermediacao_financeira",
    "bs_totalAssets",
    "bs_total_assets",
    "ativos_totais_banco_brl",
}

EQUITY_CANDIDATES = [
    "patrimonio_liquido", "patrimônio_liquido", "pl", "PL", "equity", "Equity",
    "bs_totalEquity", "bs_total_equity", "bs_stockholdersEquity", "bs_shareholdersEquity",
    "bs_totalStockholdersEquity", "bs_totalShareholdersEquity",
]

ASSET_CANDIDATES = [
    "bs_totalAssets", "bs_total_assets", "ativos_totais_banco_brl",
]

NET_INCOME_CANDIDATES = [
    "is_netIncomeFromContinuingOps", "is_netIncome", "lucro_liquido", "net_income",
    "is_incomeBeforeStatutoryParticipationsAndContributions",
]

NIM_NUMERATOR_CANDIDATES = [
    "resultado_de_intermediacao_financeira",
]


# =========================
# Utilitários de leitura e limpeza
# =========================

def split_cli_list(value: str | None) -> list[str]:
    if value is None or str(value).strip() == "":
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def first_existing(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    cols = list(columns)
    lower_map = {str(c).lower(): c for c in cols}
    for cand in candidates:
        if cand in cols:
            return cand
        key = str(cand).lower()
        if key in lower_map:
            return lower_map[key]
    return None


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().replace("\ufeff", "") for c in out.columns]
    return out


def carregar_base(path: Path, sheet: str | int | None = None) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    suffix = path.suffix.lower()
    if suffix in [".xlsx", ".xls"]:
        # Para a base_un_ajustada, a aba esperada é base_corrigida.
        # Se --sheet não for informado, usa a primeira aba.
        if sheet is None:
            df = pd.read_excel(path)
        else:
            df = pd.read_excel(path, sheet_name=sheet)
    elif suffix == ".csv":
        # sep=None tenta detectar vírgula/ponto-e-vírgula automaticamente.
        df = pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig")
    elif suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        raise ValueError("Formato não suportado. Use .xlsx, .xls, .csv ou .parquet.")

    return clean_column_names(df)


def converter_numericas(df: pd.DataFrame) -> pd.DataFrame:
    """Converte colunas textuais que pareçam numéricas, aceitando decimal com vírgula."""
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_object_dtype(out[col]) or pd.api.types.is_string_dtype(out[col]):
            s = out[col]
            non_null = s.dropna().astype(str)
            if non_null.empty:
                continue

            # Só tenta conversão agressiva se a maioria dos valores parecer numérica.
            sample = non_null.head(200)
            numeric_like = sample.str.match(r"^\s*-?\d{1,3}(?:[\.\s]?\d{3})*(?:,\d+)?\s*$|^\s*-?\d+(?:[\.,]\d+)?\s*$").mean()
            if numeric_like >= 0.75:
                cleaned = (
                    s.astype(str)
                    .str.replace("\u00a0", "", regex=False)
                    .str.replace(" ", "", regex=False)
                )
                # Trata padrão brasileiro: 1.234,56 -> 1234.56.
                cleaned = cleaned.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
                out[col] = pd.to_numeric(cleaned, errors="coerce")
            else:
                converted = pd.to_numeric(s, errors="coerce")
                # Mantém a conversão apenas se não destruir muitos dados.
                if converted.notna().sum() >= max(1, int(0.75 * s.notna().sum())):
                    out[col] = converted

    out = out.replace([np.inf, -np.inf], np.nan)
    return out


def safe_divide(num: pd.Series, den: pd.Series) -> pd.Series:
    num = pd.to_numeric(num, errors="coerce")
    den = pd.to_numeric(den, errors="coerce")
    out = num / den.replace({0: np.nan})
    return out.replace([np.inf, -np.inf], np.nan)


def criar_dependentes_derivadas(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Cria ROA, NIM e, se possível, ROE. Retorna df e logs."""
    out = df.copy()
    logs: list[str] = []

    asset_col = first_existing(out.columns, ASSET_CANDIDATES)
    net_income_col = first_existing(out.columns, NET_INCOME_CANDIDATES)
    equity_col = first_existing(out.columns, EQUITY_CANDIDATES)
    nim_num_col = first_existing(out.columns, NIM_NUMERATOR_CANDIDATES)

    if "ROA" not in out.columns:
        if net_income_col and asset_col:
            out["ROA"] = safe_divide(out[net_income_col], out[asset_col])
            logs.append(f"ROA criado como {net_income_col} / {asset_col}.")
        else:
            logs.append("ROA não criado: faltam lucro líquido e/ou ativos totais.")

    if "NIM" not in out.columns:
        if nim_num_col and asset_col:
            out["NIM"] = safe_divide(out[nim_num_col], out[asset_col])
            logs.append(f"NIM criado como {nim_num_col} / {asset_col}.")
        elif {"receitas_de_intermediacao_financeira", "despesas_de_intermediacao_financeira"}.issubset(out.columns) and asset_col:
            numerador = out["receitas_de_intermediacao_financeira"] + out["despesas_de_intermediacao_financeira"]
            out["NIM"] = safe_divide(numerador, out[asset_col])
            logs.append("NIM criado como (receitas_de_intermediacao_financeira + despesas_de_intermediacao_financeira) / ativos totais.")
        else:
            logs.append("NIM não criado: falta resultado de intermediação financeira e/ou ativos totais.")

    if "ROE" not in out.columns:
        if net_income_col and equity_col:
            out["ROE"] = safe_divide(out[net_income_col], out[equity_col])
            logs.append(f"ROE criado como {net_income_col} / {equity_col}.")
        else:
            logs.append("ROE não criado: não foi encontrada coluna de patrimônio líquido/equity na base.")

    return out, logs


def identificar_colunas(df: pd.DataFrame, dep_vars_cli: list[str] | None = None):
    id_col = first_existing(df.columns, ID_CANDIDATES)
    time_col = first_existing(df.columns, TIME_CANDIDATES)
    if dep_vars_cli:
        deps = [c for c in dep_vars_cli if c in df.columns]
    else:
        deps = [c for c in DEPENDENT_CANDIDATES if c in df.columns]
    return id_col, time_col, deps


# =========================
# Seleção e preparação da amostra
# =========================

def selecionar_regressores(
    df: pd.DataFrame,
    dep_var: str,
    x_vars_cli: list[str] | None = None,
    x_mode: str = "m1",
    drop_missing_pct: float = 0.95,
):
    dropped: list[tuple[str, str]] = []

    if x_vars_cli:
        x_cols = []
        for c in x_vars_cli:
            if c in df.columns:
                x_cols.append(c)
            else:
                dropped.append((c, "variável solicitada em --x-vars não existe na base"))
    elif x_mode == "m1":
        # Evita duplicidade entre medidas de tamanho e entre hhi em decimal e 10000.
        candidates = []
        for c in DEFAULT_M1_REGRESSORS:
            if c not in df.columns:
                dropped.append((c, "regressor M1 não encontrado na base"))
                continue
            candidates.append(c)

        # Se as duas medidas de tamanho estiverem presentes, usa bs_totalAssets_log.
        if "bs_totalAssets_log" in candidates and "ativos_totais_banco_brl_log" in candidates:
            candidates.remove("ativos_totais_banco_brl_log")
            dropped.append(("ativos_totais_banco_brl_log", "removido por duplicidade com bs_totalAssets_log"))

        # Se as duas escalas de HHI estiverem presentes, usa a versão decimal.
        if "hhi_periodo_corrigido_dec" in candidates and "hhi_periodo_corrigido_10000" in candidates:
            candidates.remove("hhi_periodo_corrigido_10000")
            dropped.append(("hhi_periodo_corrigido_10000", "removido por duplicidade com hhi_periodo_corrigido_dec"))

        x_cols = candidates
    elif x_mode == "all_numeric":
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        exclude = set(EXCLUDE_AS_X_BASE) | DEPENDENT_COMPONENTS | {dep_var}
        x_cols = [c for c in numeric_cols if c not in exclude]
    else:
        raise ValueError("x_mode inválido. Use 'm1' ou 'all_numeric'.")

    valid_x = []
    for c in x_cols:
        if c == dep_var:
            continue
        if c not in df.columns:
            dropped.append((c, "não encontrada"))
            continue
        if not pd.api.types.is_numeric_dtype(df[c]):
            dropped.append((c, "não numérica"))
            continue
        non_na = df[c].dropna()
        if non_na.empty:
            dropped.append((c, "todos os valores ausentes"))
            continue
        if non_na.nunique() <= 1:
            dropped.append((c, "sem variância"))
            continue
        missing_pct = float(df[c].isna().mean())
        if missing_pct > drop_missing_pct:
            dropped.append((c, f"missing acima do limite ({missing_pct:.1%})"))
            continue
        valid_x.append(c)

    # Remove duplicatas preservando ordem.
    valid_x = list(dict.fromkeys(valid_x))
    return valid_x, dropped


def preparar_amostra(
    df: pd.DataFrame,
    dep_var: str,
    x_cols: list[str],
    id_col: str | None,
    time_col: str | None,
    impute_x: str = "none",
):
    cols = [dep_var] + x_cols
    if id_col:
        cols.append(id_col)
    if time_col and time_col not in cols:
        cols.append(time_col)

    base = df[cols].copy().replace([np.inf, -np.inf], np.nan)

    sort_cols = [c for c in [id_col, time_col] if c is not None and c in base.columns]
    if sort_cols:
        base = base.sort_values(sort_cols)

    # y nunca é imputado.
    base = base.dropna(subset=[dep_var]).copy()

    if impute_x == "median":
        for c in x_cols:
            med = base[c].median(skipna=True)
            if pd.notna(med):
                base[c] = base[c].fillna(med)
        base = base.dropna(subset=x_cols).copy()
    elif impute_x == "zero":
        base[x_cols] = base[x_cols].fillna(0)
        base = base.dropna(subset=x_cols).copy()
    elif impute_x == "none":
        base = base.dropna(subset=x_cols).copy()
    else:
        raise ValueError("impute_x inválido. Use none, median ou zero.")

    # Remove linhas remanescentes não finitas.
    numeric = [dep_var] + x_cols
    mask = np.isfinite(base[numeric].astype(float).to_numpy()).all(axis=1)
    base = base.loc[mask].copy()
    return base


def reduzir_colinearidade_perfeita(X: pd.DataFrame, tol: float = 1e-12) -> tuple[pd.DataFrame, list[tuple[str, str]]]:
    """Remove colunas duplicadas/perfeitamente colineares quando detectáveis de modo simples."""
    dropped: list[tuple[str, str]] = []
    out = X.copy()

    # Remove duplicatas exatas.
    dup_mask = out.T.duplicated()
    for col in out.columns[dup_mask]:
        dropped.append((col, "duplicata exata de outro regressor na amostra"))
    out = out.loc[:, ~dup_mask]

    # Remove colunas com correlação perfeita absoluta com coluna anterior.
    corr = out.corr().abs()
    to_drop = set()
    cols = list(out.columns)
    for i in range(len(cols)):
        if cols[i] in to_drop:
            continue
        for j in range(i + 1, len(cols)):
            if cols[j] in to_drop:
                continue
            val = corr.iloc[i, j]
            if pd.notna(val) and abs(float(val) - 1.0) <= tol:
                to_drop.add(cols[j])
                dropped.append((cols[j], f"correlação perfeita com {cols[i]}"))
    if to_drop:
        out = out.drop(columns=list(to_drop))

    return out, dropped


# =========================
# Testes estatísticos
# =========================

def calcular_vif(X: pd.DataFrame) -> pd.DataFrame:
    if X.empty:
        return pd.DataFrame([{"erro": "sem regressores"}])
    Xc = sm.add_constant(X, has_constant="add")
    rows = []
    values = Xc.values.astype(float)
    for i, col in enumerate(Xc.columns):
        if col == "const":
            continue
        try:
            vif = variance_inflation_factor(values, i)
        except Exception:
            vif = np.nan
        rows.append({"variavel": col, "VIF": vif})
    return pd.DataFrame(rows).sort_values("VIF", ascending=False)


def pooled_ols(y: pd.Series, X: pd.DataFrame):
    Xc = sm.add_constant(X, has_constant="add")
    model = sm.OLS(y.astype(float), Xc.astype(float), missing="drop")
    res = model.fit()
    return res, Xc


def fe_lsdv(y: pd.Series, X: pd.DataFrame, groups: pd.Series):
    dummies = pd.get_dummies(groups.astype(str), prefix="fe", drop_first=True, dtype=float)
    X_fe = pd.concat([X.reset_index(drop=True), dummies.reset_index(drop=True)], axis=1)
    X_fe = sm.add_constant(X_fe, has_constant="add")
    model = sm.OLS(y.reset_index(drop=True).astype(float), X_fe.astype(float), missing="drop")
    res = model.fit()
    return res, X_fe, dummies.columns.tolist()


def re_mixedlm(y: pd.Series, X: pd.DataFrame, groups: pd.Series):
    Xc = sm.add_constant(X, has_constant="add")
    model = MixedLM(endog=y.astype(float), exog=Xc.astype(float), groups=groups.astype(str))
    try:
        res = model.fit(reml=False, method="lbfgs", maxiter=1000, disp=False)
    except Exception:
        # Fallback útil em algumas bases pequenas/colineares.
        res = model.fit(reml=False, method="powell", maxiter=1000, disp=False)
    return res, Xc


def mixedlm_fixo_aleatorio(
    y: pd.Series,
    X: pd.DataFrame,
    groups: pd.Series,
    random_slopes: list[str] | None = None,
):
    """
    Estima modelo misto por MixedLM.

    Interpretação:
    - efeitos fixos: coeficientes médios dos regressores em X;
    - efeitos aleatórios: intercepto específico por instituição;
    - opcionalmente, inclinações aleatórias para variáveis informadas em
      --mixed-random-slopes.
    """
    Xc = sm.add_constant(X, has_constant="add")

    random_slopes = [c for c in (random_slopes or []) if c in X.columns]
    if random_slopes:
        exog_re = sm.add_constant(X[random_slopes], has_constant="add")
        estrutura = "intercepto aleatório + inclinações aleatórias: " + ", ".join(random_slopes)
    else:
        exog_re = None
        estrutura = "intercepto aleatório por instituição"

    model = MixedLM(
        endog=y.astype(float),
        exog=Xc.astype(float),
        groups=groups.astype(str),
        exog_re=None if exog_re is None else exog_re.astype(float),
    )
    try:
        res = model.fit(reml=False, method="lbfgs", maxiter=1500, disp=False)
    except Exception:
        res = model.fit(reml=False, method="powell", maxiter=1500, disp=False)
    return res, Xc, estrutura


def resultado_robusto_cluster(res, groups: pd.Series):
    """Retorna resultados OLS com covariância robusta clusterizada por instituição."""
    groups_clean = pd.Series(groups).reset_index(drop=True).astype(str)
    try:
        return res.get_robustcov_results(
            cov_type="cluster",
            groups=groups_clean,
            use_correction=True,
            df_correction=True,
        )
    except TypeError:
        # Compatibilidade com versões antigas do statsmodels.
        return res.get_robustcov_results(cov_type="cluster", groups=groups_clean)


def resumo_cluster(groups: pd.Series, cluster_col: str | None = None) -> pd.DataFrame:
    g = pd.Series(groups).astype(str)
    counts = g.value_counts().sort_index()
    return pd.DataFrame([{
        "cluster_col": cluster_col or "grupo",
        "n_clusters": int(counts.shape[0]),
        "min_obs_cluster": int(counts.min()),
        "media_obs_cluster": float(counts.mean()),
        "max_obs_cluster": int(counts.max()),
        "observacao": "Erros-padrão robustos clusterizados por instituição; recomendados quando há heterocedasticidade e dependência intra-instituição."
    }])


def efeitos_aleatorios_mixedlm(res, nome: str = "mixedlm") -> pd.DataFrame:
    try:
        rows = []
        for entidade, valores in res.random_effects.items():
            if isinstance(valores, pd.Series):
                item = {"modelo": nome, "entidade": entidade}
                for k, v in valores.items():
                    item[f"efeito_aleatorio_{k}"] = float(v)
                rows.append(item)
            else:
                arr = np.asarray(valores).reshape(-1)
                item = {"modelo": nome, "entidade": entidade}
                for i, v in enumerate(arr):
                    item[f"efeito_aleatorio_{i}"] = float(v)
                rows.append(item)
        return pd.DataFrame(rows) if rows else pd.DataFrame([{
            "modelo": nome, "observacao": "sem efeitos aleatórios retornados"
        }])
    except Exception as e:
        return pd.DataFrame([{"modelo": nome, "erro": str(e)}])


def componentes_variancia_mixedlm(res, nome: str, estrutura: str) -> pd.DataFrame:
    rows = []
    try:
        rows.append({
            "modelo": nome,
            "componente": "residual_scale",
            "valor": float(getattr(res, "scale", np.nan)),
            "estrutura": estrutura,
            "converged": bool(getattr(res, "converged", False)),
        })
    except Exception:
        pass

    try:
        cov_re = res.cov_re
        if isinstance(cov_re, pd.DataFrame):
            for i in cov_re.index:
                for j in cov_re.columns:
                    rows.append({
                        "modelo": nome,
                        "componente": f"cov_re[{i},{j}]",
                        "valor": float(cov_re.loc[i, j]),
                        "estrutura": estrutura,
                        "converged": bool(getattr(res, "converged", False)),
                    })
        else:
            arr = np.asarray(cov_re)
            for i in range(arr.shape[0]):
                for j in range(arr.shape[1]):
                    rows.append({
                        "modelo": nome,
                        "componente": f"cov_re[{i},{j}]",
                        "valor": float(arr[i, j]),
                        "estrutura": estrutura,
                        "converged": bool(getattr(res, "converged", False)),
                    })
    except Exception as e:
        rows.append({
            "modelo": nome,
            "componente": "cov_re",
            "valor": np.nan,
            "estrutura": estrutura,
            "converged": bool(getattr(res, "converged", False)),
            "erro": str(e),
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame([{
        "modelo": nome, "estrutura": estrutura, "observacao": "componentes de variância indisponíveis"
    }])


def teste_white(res_pooled, Xc: pd.DataFrame) -> pd.DataFrame:
    lm_stat, lm_pvalue, f_stat, f_pvalue = het_white(res_pooled.resid, Xc.astype(float))
    return pd.DataFrame([{
        "teste": "White",
        "LM": lm_stat,
        "p_valor_LM": lm_pvalue,
        "F": f_stat,
        "p_valor_F": f_pvalue,
        "observacao": "H0: homocedasticidade; rejeição sugere heterocedasticidade"
    }])


def teste_bp_hetero(res_pooled, Xc: pd.DataFrame) -> pd.DataFrame:
    lm_stat, lm_pvalue, f_stat, f_pvalue = het_breuschpagan(res_pooled.resid, Xc.astype(float))
    return pd.DataFrame([{
        "teste": "Breusch-Pagan (heterocedasticidade)",
        "LM": lm_stat,
        "p_valor_LM": lm_pvalue,
        "F": f_stat,
        "p_valor_F": f_pvalue,
        "observacao": "H0: homocedasticidade; rejeição sugere heterocedasticidade"
    }])


def teste_chow_poolability(res_pooled, res_fe, n_groups: int) -> pd.DataFrame:
    rss_pooled = float(np.sum(res_pooled.resid ** 2))
    rss_fe = float(np.sum(res_fe.resid ** 2))

    q = max(n_groups - 1, 1)
    df_den = int(res_fe.df_resid)

    if df_den <= 0:
        return pd.DataFrame([{
            "teste": "Chow / Poolability",
            "F": np.nan,
            "gl_num": q,
            "gl_den": df_den,
            "p_valor": np.nan,
            "observacao": "graus de liberdade insuficientes"
        }])

    num = (rss_pooled - rss_fe) / q
    den = rss_fe / df_den
    if den <= 0:
        f_stat = np.nan
        p_value = np.nan
    else:
        f_stat = num / den
        p_value = 1 - stats.f.cdf(f_stat, q, df_den)

    return pd.DataFrame([{
        "teste": "Chow / Poolability (pooled vs FE)",
        "F": f_stat,
        "gl_num": q,
        "gl_den": df_den,
        "p_valor": p_value,
        "observacao": "H0: pooled OLS é suficiente; rejeição favorece FE"
    }])


def teste_hausman(fe_res, re_res, slope_cols: list[str]) -> pd.DataFrame:
    common = [c for c in slope_cols if c in fe_res.params.index and c in re_res.params.index]
    if not common:
        return pd.DataFrame([{
            "teste": "Hausman",
            "qui2": np.nan,
            "gl": 0,
            "p_valor": np.nan,
            "observacao": "sem coeficientes comuns comparáveis"
        }])

    b_fe = fe_res.params[common].astype(float)
    b_re = re_res.params[common].astype(float)

    v_fe = fe_res.cov_params().loc[common, common].astype(float)
    v_re = re_res.cov_params().loc[common, common].astype(float)

    diff_b = b_fe - b_re
    diff_v = v_fe - v_re

    try:
        inv = np.linalg.pinv(diff_v.values)
        stat = float(diff_b.values.T @ inv @ diff_b.values)
        gl = len(common)
        p_value = 1 - stats.chi2.cdf(stat, gl)
        obs = "H0: RE é consistente; rejeição favorece FE"
    except Exception as e:
        stat = np.nan
        gl = len(common)
        p_value = np.nan
        obs = f"falha na inversão da matriz: {e}"

    return pd.DataFrame([{
        "teste": "Hausman (FE vs RE)",
        "qui2": stat,
        "gl": gl,
        "p_valor": p_value,
        "observacao": obs
    }])


def teste_bp_lm_re_aprox(res_pooled, groups: pd.Series) -> pd.DataFrame:
    e = pd.Series(np.asarray(res_pooled.resid).reshape(-1), index=groups.index)
    temp = pd.DataFrame({"g": groups.values, "e": e.values})

    counts = temp.groupby("g").size()
    n_groups = int(counts.shape[0])

    if n_groups < 2:
        return pd.DataFrame([{
            "teste": "Breusch-Pagan LM (efeitos aleatórios)",
            "LM": np.nan,
            "gl": 1,
            "p_valor": np.nan,
            "observacao": "menos de 2 grupos; teste não aplicável"
        }])

    balanced = counts.nunique() == 1
    T = float(counts.iloc[0] if balanced else counts.mean())

    if T <= 1:
        return pd.DataFrame([{
            "teste": "Breusch-Pagan LM (efeitos aleatórios)",
            "LM": np.nan,
            "gl": 1,
            "p_valor": np.nan,
            "observacao": "T <= 1; teste não aplicável"
        }])

    sum_e_by_g = temp.groupby("g")["e"].sum()
    num = float(np.sum(sum_e_by_g ** 2))
    den = float(np.sum(temp["e"] ** 2))
    if den == 0:
        return pd.DataFrame([{
            "teste": "Breusch-Pagan LM (efeitos aleatórios)",
            "LM": np.nan,
            "gl": 1,
            "p_valor": np.nan,
            "observacao": "soma dos quadrados dos resíduos igual a zero"
        }])

    A = num / den
    lm = (n_groups * T / (2 * (T - 1))) * ((A - 1) ** 2)
    p_value = 1 - stats.chi2.cdf(lm, 1)

    obs = "H0: pooled OLS é suficiente; rejeição favorece RE"
    if not balanced:
        obs += " | painel desbalanceado: estatística reportada como aproximação"

    return pd.DataFrame([{
        "teste": "Breusch-Pagan LM (pooled vs RE)",
        "LM": lm,
        "gl": 1,
        "p_valor": p_value,
        "observacao": obs
    }])


def resumo_modelo(res, nome: str) -> pd.DataFrame:
    items = {
        "modelo": nome,
        "nobs": getattr(res, "nobs", np.nan),
        "r2": getattr(res, "rsquared", np.nan),
        "r2_adj": getattr(res, "rsquared_adj", np.nan),
        "llf": getattr(res, "llf", np.nan),
        "aic": getattr(res, "aic", np.nan),
        "bic": getattr(res, "bic", np.nan),
    }
    return pd.DataFrame([items])


def _series_com_nomes(res, values, default_prefix: str = "param") -> pd.Series:
    """Converte arrays de resultados em Series com nomes de parâmetros."""
    if isinstance(values, pd.Series):
        return values.astype(float)

    arr = np.asarray(values, dtype=float).reshape(-1)
    names = None
    try:
        names = list(res.params.index) if isinstance(res.params, pd.Series) else None
    except Exception:
        names = None
    if names is None or len(names) != len(arr):
        try:
            names = list(res.model.exog_names)
        except Exception:
            names = None
    if names is None or len(names) != len(arr):
        names = [f"{default_prefix}_{i}" for i in range(len(arr))]
    return pd.Series(arr, index=names, dtype=float)


def coeficientes_modelo(res, nome: str, cov_tipo: str = "convencional") -> pd.DataFrame:
    try:
        params = _series_com_nomes(res, res.params, default_prefix="param")
        bse = _series_com_nomes(res, getattr(res, "bse", np.repeat(np.nan, len(params))), default_prefix="param")
        pvalues = _series_com_nomes(res, getattr(res, "pvalues", np.repeat(np.nan, len(params))), default_prefix="param")

        stat_raw = getattr(res, "tvalues", None)
        if stat_raw is None:
            stat_raw = getattr(res, "zvalues", np.repeat(np.nan, len(params)))
        estatistica = _series_com_nomes(res, stat_raw, default_prefix="param")

        return pd.DataFrame({
            "modelo": nome,
            "cov_tipo": cov_tipo,
            "variavel": params.index,
            "coeficiente": params.values,
            "erro_padrao": bse.reindex(params.index).values,
            "estatistica": estatistica.reindex(params.index).values,
            "p_valor": pvalues.reindex(params.index).values,
        })
    except Exception as e:
        return pd.DataFrame([{"modelo": nome, "cov_tipo": cov_tipo, "erro": str(e)}])


# =========================
# Saídas
# =========================

def safe_sheet_name(name: str, used: set[str]) -> str:
    cleaned = re.sub(r"[\\/*?:\[\]]", "_", name)[:31]
    base = cleaned or "Sheet"
    candidate = base
    i = 1
    while candidate in used:
        suffix = f"_{i}"
        candidate = f"{base[:31-len(suffix)]}{suffix}"
        i += 1
    used.add(candidate)
    return candidate


def salvar_excel(
    output_xlsx: Path,
    info_base: pd.DataFrame,
    logs: pd.DataFrame,
    resultados: dict[str, dict[str, pd.DataFrame]],
):
    output_xlsx.parent.mkdir(parents=True, exist_ok=True)
    used: set[str] = set()
    with pd.ExcelWriter(output_xlsx, engine="openpyxl") as writer:
        info_base.to_excel(writer, sheet_name=safe_sheet_name("info_base", used), index=False)
        logs.to_excel(writer, sheet_name=safe_sheet_name("logs", used), index=False)

        for dep, blocos in resultados.items():
            for nome_sheet, tabela in blocos.items():
                sheet = safe_sheet_name(f"{dep[:8]}_{nome_sheet[:22]}", used)
                tabela.to_excel(writer, sheet_name=sheet, index=False)


def gerar_resumo_txt(output_txt: Path, info_base: pd.DataFrame, logs: pd.DataFrame, resultados):
    output_txt.parent.mkdir(parents=True, exist_ok=True)
    linhas = []
    linhas.append("DIAGNÓSTICOS M1 - BASE_UN_AJUSTADA\n")
    linhas.append("=" * 70 + "\n\n")
    linhas.append("Informações da base:\n")
    for _, row in info_base.iterrows():
        linhas.append(f"- {row['item']}: {row['valor']}\n")

    if not logs.empty:
        linhas.append("\nLogs e observações:\n")
        for _, row in logs.iterrows():
            dep = row.get("variavel_dependente", "geral")
            linhas.append(f"- [{dep}] {row['mensagem']}\n")

    for dep, blocos in resultados.items():
        linhas.append(f"\n\n### Variável dependente: {dep}\n")
        for nome, tabela in blocos.items():
            linhas.append(f"\n[{nome}]\n")
            if isinstance(tabela, pd.DataFrame) and not tabela.empty:
                linhas.append(tabela.to_string(index=False))
            else:
                linhas.append("Sem resultados.")
            linhas.append("\n")

    output_txt.write_text("".join(linhas), encoding="utf-8")


# =========================
# Pipeline principal
# =========================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Testes diagnósticos M1 adaptados para base_un_ajustada.")
    parser.add_argument("--input", default="base_un_ajustada.xlsx", help="Arquivo de entrada (.xlsx/.xls/.csv/.parquet)")
    parser.add_argument("--sheet", default="base_corrigida", help="Aba do Excel. Use vazio para primeira aba.")
    parser.add_argument("--dep-vars", default="", help="Dependentes separadas por vírgula. Ex.: ROA,NIM. Vazio = auto.")
    parser.add_argument("--x-vars", default="", help="Regressores separados por vírgula. Se preenchido, sobrescreve o conjunto M1 padrão.")
    parser.add_argument("--x-mode", choices=["m1", "all_numeric"], default="m1", help="Modo de seleção dos regressores quando --x-vars não é informado.")
    parser.add_argument("--drop-missing-pct", type=float, default=0.95, help="Remove regressores com missing acima desse limite. Default: 0.95")
    parser.add_argument("--impute-x", choices=["none", "median", "zero"], default="none", help="Imputação opcional apenas nos regressores. Default: none.")
    parser.add_argument("--min-nobs", type=int, default=30, help="Número mínimo de observações por modelo. Default: 30.")
    parser.add_argument("--reduce-perfect-collinearity", action="store_true", help="Remove duplicatas e correlações perfeitas entre X na amostra.")
    parser.add_argument("--no-cluster-robust", action="store_true", help="Desativa os erros-padrão robustos clusterizados por instituição.")
    parser.add_argument("--mixed-random-slopes", default="", help="Regressores com inclinação aleatória no MixedLM, separados por vírgula. Default: apenas intercepto aleatório.")
    parser.add_argument("--output-xlsx", default="diagnosticos_m1_base_un_ajustada_cluster_mixed.xlsx", help="Arquivo de saída Excel")
    parser.add_argument("--output-txt", default="diagnosticos_m1_base_un_ajustada_cluster_mixed_resumo.txt", help="Arquivo de saída texto")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    warnings.filterwarnings("ignore")

    input_path = Path(args.input)
    output_xlsx = Path(args.output_xlsx)
    output_txt = Path(args.output_txt)
    sheet = None if str(args.sheet).strip() == "" else args.sheet

    dep_vars_cli = split_cli_list(args.dep_vars)
    x_vars_cli = split_cli_list(args.x_vars)
    mixed_random_slopes_cli = split_cli_list(args.mixed_random_slopes)

    df = carregar_base(input_path, sheet=sheet)
    df = converter_numericas(df)
    df, dep_logs = criar_dependentes_derivadas(df)

    id_col, time_col, dep_vars = identificar_colunas(df, dep_vars_cli=dep_vars_cli)
    if not dep_vars:
        available = ", ".join([c for c in DEPENDENT_CANDIDATES if c in df.columns])
        raise ValueError(
            "Nenhuma variável dependente encontrada/criada entre ROA, ROE e NIM. "
            f"Dependentes disponíveis: {available or 'nenhuma'}."
        )

    logs_rows = []
    for msg in dep_logs:
        logs_rows.append({"variavel_dependente": "geral", "mensagem": msg})

    info_base = pd.DataFrame([
        {"item": "arquivo_entrada", "valor": str(input_path.resolve())},
        {"item": "aba_excel", "valor": sheet if sheet is not None else "primeira aba"},
        {"item": "n_linhas", "valor": int(df.shape[0])},
        {"item": "n_colunas", "valor": int(df.shape[1])},
        {"item": "coluna_id", "valor": id_col},
        {"item": "coluna_tempo", "valor": time_col},
        {"item": "dependentes_identificadas", "valor": ", ".join(dep_vars)},
        {"item": "modo_regressores", "valor": "x-vars manual" if x_vars_cli else args.x_mode},
        {"item": "impute_x", "valor": args.impute_x},
        {"item": "cluster_robust", "valor": "não" if args.no_cluster_robust else "sim"},
        {"item": "cluster_col", "valor": id_col},
        {"item": "mixed_random_slopes", "valor": ", ".join(mixed_random_slopes_cli) if mixed_random_slopes_cli else "nenhuma"},
    ])

    resultados: dict[str, dict[str, pd.DataFrame]] = {}

    for dep_var in dep_vars:
        x_cols, dropped = selecionar_regressores(
            df,
            dep_var,
            x_vars_cli=x_vars_cli,
            x_mode=args.x_mode,
            drop_missing_pct=args.drop_missing_pct,
        )

        for c, motivo in dropped:
            logs_rows.append({
                "variavel_dependente": dep_var,
                "mensagem": f"Regressor descartado: {c} ({motivo})",
            })

        blocos: dict[str, pd.DataFrame] = {}

        if not x_cols:
            logs_rows.append({
                "variavel_dependente": dep_var,
                "mensagem": "Nenhum regressor válido após filtragem.",
            })
            resultados[dep_var] = blocos
            continue

        base = preparar_amostra(df, dep_var, x_cols, id_col, time_col, impute_x=args.impute_x)

        if base.shape[0] < args.min_nobs:
            logs_rows.append({
                "variavel_dependente": dep_var,
                "mensagem": f"Amostra insuficiente após tratamento de ausências: n={base.shape[0]}, mínimo={args.min_nobs}.",
            })
            resultados[dep_var] = {
                "amostra": pd.DataFrame({
                    "variavel": [dep_var] + x_cols,
                    "tipo": ["dependente"] + ["regressor"] * len(x_cols),
                    "n_original_nao_nulo": [df[dep_var].notna().sum()] + [df[c].notna().sum() for c in x_cols],
                })
            }
            continue

        y = base[dep_var].astype(float)
        X = base[x_cols].astype(float)

        if args.reduce_perfect_collinearity:
            X, collin_dropped = reduzir_colinearidade_perfeita(X)
            for c, motivo in collin_dropped:
                logs_rows.append({
                    "variavel_dependente": dep_var,
                    "mensagem": f"Regressor descartado na amostra: {c} ({motivo})",
                })
            x_cols = list(X.columns)

        if X.empty or base.shape[0] <= X.shape[1] + 2:
            logs_rows.append({
                "variavel_dependente": dep_var,
                "mensagem": f"Graus de liberdade insuficientes: n={base.shape[0]}, k={X.shape[1]}.",
            })
            resultados[dep_var] = {}
            continue

        blocos["amostra"] = pd.DataFrame({
            "variavel": [dep_var] + x_cols,
            "tipo": ["dependente"] + ["regressor"] * len(x_cols),
            "n_modelo": [int(y.notna().sum())] + [int(X[c].notna().sum()) for c in x_cols],
            "media_modelo": [float(y.mean())] + [float(X[c].mean()) for c in x_cols],
            "desvio_padrao_modelo": [float(y.std())] + [float(X[c].std()) for c in x_cols],
        })

        if id_col and id_col in base.columns:
            counts = base.groupby(id_col).size().describe().to_frame("obs_por_entidade")
            blocos["painel_resumo"] = pd.DataFrame({
                "item": ["n_observacoes", "n_entidades", "min_obs_entidade", "media_obs_entidade", "max_obs_entidade"],
                "valor": [
                    int(base.shape[0]),
                    int(base[id_col].nunique()),
                    int(base.groupby(id_col).size().min()),
                    float(base.groupby(id_col).size().mean()),
                    int(base.groupby(id_col).size().max()),
                ],
            })

        # 1) VIF
        try:
            blocos["vif"] = calcular_vif(X)
        except Exception as e:
            blocos["vif"] = pd.DataFrame([{"erro": str(e)}])

        # 2) pooled OLS e testes de heterocedasticidade
        pooled_res = None
        pooled_Xc = None
        try:
            pooled_res, pooled_Xc = pooled_ols(y, X)
            blocos["pooled_resumo"] = resumo_modelo(pooled_res, "pooled_ols")
            blocos["pooled_coef"] = coeficientes_modelo(pooled_res, "pooled_ols")
            if (not args.no_cluster_robust) and id_col and id_col in base.columns:
                try:
                    pooled_cluster_res = resultado_robusto_cluster(pooled_res, base[id_col])
                    blocos["pooled_coef_cluster"] = coeficientes_modelo(
                        pooled_cluster_res,
                        "pooled_ols_cluster_entidade",
                        cov_tipo="cluster_entidade",
                    )
                    blocos["cluster_info"] = resumo_cluster(base[id_col], cluster_col=id_col)
                except Exception as e:
                    blocos["pooled_coef_cluster"] = pd.DataFrame([{"erro": str(e)}])
            blocos["white"] = teste_white(pooled_res, pooled_Xc)
            blocos["bp_hetero"] = teste_bp_hetero(pooled_res, pooled_Xc)
        except Exception as e:
            blocos["pooled_resumo"] = pd.DataFrame([{"erro": str(e)}])
            blocos["pooled_coef"] = pd.DataFrame([{"erro": str(e)}])
            blocos["white"] = pd.DataFrame([{"erro": str(e)}])
            blocos["bp_hetero"] = pd.DataFrame([{"erro": str(e)}])

        # 3) Testes de painel
        if id_col and id_col in base.columns and base[id_col].nunique() >= 2:
            groups = base[id_col]

            # FE via LSDV e Chow
            try:
                fe_res, _, _ = fe_lsdv(y, X, groups)
                blocos["fe_resumo"] = resumo_modelo(fe_res, "fe_lsdv")
                blocos["fe_coef"] = coeficientes_modelo(fe_res, "fe_lsdv")
                if not args.no_cluster_robust:
                    try:
                        fe_cluster_res = resultado_robusto_cluster(fe_res, groups)
                        blocos["fe_coef_cluster"] = coeficientes_modelo(
                            fe_cluster_res,
                            "fe_lsdv_cluster_entidade",
                            cov_tipo="cluster_entidade",
                        )
                    except Exception as e:
                        blocos["fe_coef_cluster"] = pd.DataFrame([{"erro": str(e)}])
                if pooled_res is not None:
                    blocos["chow"] = teste_chow_poolability(pooled_res, fe_res, groups.nunique())
                else:
                    blocos["chow"] = pd.DataFrame([{"erro": "pooled OLS indisponível"}])
            except Exception as e:
                fe_res = None
                blocos["fe_resumo"] = pd.DataFrame([{"erro": str(e)}])
                blocos["fe_coef"] = pd.DataFrame([{"erro": str(e)}])
                blocos["chow"] = pd.DataFrame([{"erro": str(e)}])

            # RE via MixedLM e modelo misto explícito
            try:
                re_res, _ = re_mixedlm(y, X, groups)
                blocos["re_resumo"] = resumo_modelo(re_res, "random_intercept_mixedlm")
                blocos["re_coef"] = coeficientes_modelo(re_res, "random_intercept_mixedlm")
            except Exception as e:
                re_res = None
                blocos["re_resumo"] = pd.DataFrame([{"erro": str(e)}])
                blocos["re_coef"] = pd.DataFrame([{"erro": str(e)}])

            try:
                random_slopes_validas = [c for c in mixed_random_slopes_cli if c in X.columns]
                random_slopes_invalidas = [c for c in mixed_random_slopes_cli if c not in X.columns]
                for c in random_slopes_invalidas:
                    logs_rows.append({
                        "variavel_dependente": dep_var,
                        "mensagem": f"Inclinação aleatória ignorada no MixedLM: {c} não está em X.",
                    })

                mixed_res, _, mixed_estrutura = mixedlm_fixo_aleatorio(
                    y, X, groups, random_slopes=random_slopes_validas
                )
                blocos["mixed_resumo"] = resumo_modelo(mixed_res, "mixedlm_fixed_random")
                blocos["mixed_coef"] = coeficientes_modelo(mixed_res, "mixedlm_fixed_random")
                blocos["mixed_varcomp"] = componentes_variancia_mixedlm(
                    mixed_res, "mixedlm_fixed_random", mixed_estrutura
                )
                blocos["mixed_random_effects"] = efeitos_aleatorios_mixedlm(
                    mixed_res, "mixedlm_fixed_random"
                )
            except Exception as e:
                blocos["mixed_resumo"] = pd.DataFrame([{"erro": str(e)}])
                blocos["mixed_coef"] = pd.DataFrame([{"erro": str(e)}])
                blocos["mixed_varcomp"] = pd.DataFrame([{"erro": str(e)}])
                blocos["mixed_random_effects"] = pd.DataFrame([{"erro": str(e)}])

            # Hausman
            try:
                if fe_res is not None and re_res is not None:
                    blocos["hausman"] = teste_hausman(fe_res, re_res, x_cols)
                else:
                    blocos["hausman"] = pd.DataFrame([{"erro": "FE ou RE indisponível"}])
            except Exception as e:
                blocos["hausman"] = pd.DataFrame([{"erro": str(e)}])

            # BP-LM para RE
            try:
                if pooled_res is not None:
                    blocos["bp_lm_re"] = teste_bp_lm_re_aprox(pooled_res, groups)
                else:
                    blocos["bp_lm_re"] = pd.DataFrame([{"erro": "pooled OLS indisponível"}])
            except Exception as e:
                blocos["bp_lm_re"] = pd.DataFrame([{"erro": str(e)}])
        else:
            msg = "Sem coluna identificadora de painel ou menos de 2 entidades; testes de Chow/Hausman/BP-LM não executados."
            logs_rows.append({"variavel_dependente": dep_var, "mensagem": msg})

        resultados[dep_var] = blocos

    logs = pd.DataFrame(logs_rows) if logs_rows else pd.DataFrame(columns=["variavel_dependente", "mensagem"])
    salvar_excel(output_xlsx, info_base, logs, resultados)
    gerar_resumo_txt(output_txt, info_base, logs, resultados)

    print("Concluído.")
    print("Saídas:")
    print(f"- {output_xlsx.resolve()}")
    print(f"- {output_txt.resolve()}")


if __name__ == "__main__":
    main()
