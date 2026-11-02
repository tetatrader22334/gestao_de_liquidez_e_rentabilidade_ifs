#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Difference GMM / System GMM para painel dinâmico de rentabilidade bancária.

Base esperada: base_final.xlsx, com painel identificado por:
    - entidade: id_entidade
    - tempo: AnoMes_ord

Modelo padrão:
    y_it = rho*y_i,t-1 + beta*liquidez_it + gamma*controles_it + mu_i + e_it

Estimador:
    - Difference GMM: Arellano-Bond, com opção `nolevel` no pydynpd.
    - System GMM: Arellano-Bover/Blundell-Bond, padrão do pydynpd.

Dependências:
    pip install pandas numpy openpyxl scipy prettytable pydynpd

Exemplos de uso:
    python 17_gmm_difference_system_base_final.py --input bases/base_final.xlsx --dep ROA --timedumm --mode both --output-dir "outputs/modelos/M2 - GMM/liquidez_regulatoria"

Observações metodológicas:
    1) O script limita defasagens e usa instrumentos colapsados por padrão para reduzir proliferação de instrumentos.
    2) Variáveis invariantes dentro da instituição são removidas automaticamente do Difference GMM.
    3) Se `--timedumm` for usado, o script remove controles constantes por período, pois ficariam colineares
       com dummies temporais.
    4) Interpretação mínima dos diagnósticos:
       - AR(1): geralmente esperado significativo em diferenças.
       - AR(2): desejável não significativo.
       - Hansen: desejável não rejeitar; p muito alto pode indicar excesso de instrumentos.
       - Nº de instrumentos: idealmente menor que o nº de grupos.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Dict, Tuple, Optional

import numpy as np
import pandas as pd

try:
    from pydynpd import regression
except ImportError as exc:  # pragma: no cover
    regression = None
    PYDYNPD_IMPORT_ERROR = exc
else:
    PYDYNPD_IMPORT_ERROR = None


DEFAULT_PREDETERMINED = [
    # Variáveis centrais de gestão de liquidez e estrutura prudencial
    "lcr_dec",
    "nsfr_dec",
    # "indice_de_basileia_dec",
    # "indice_de_imobilizacao_dec",
    # Controles bancários potencialmente simultâneos/predeterminados
    # "ativo_total_log",
    # "market_share_dec",
    # "operacoes_de_credito_ativo_total",
    # "provisoes_de_credito_sobre_ativo_total",
    # "despesas_adm_sobre_receitas",
    # "despesas_de_intermediacao_sobre_receitas",
]

DEFAULT_STRICT_IV = [
    # Controles macroeconômicos e dummies de crise/controle
    # "selic_media_trimestre_dec",
    # "ipca_media_trimestre_dec",
    # "pib_indice_sa_log",
    # "hhi_periodo_dec",
    # "estatal",
    # "controle_estrangeiro",
    # "crise_nme",
    # "crise_covid",
]

DEFAULT_DEPENDENTS = ["ROA", "ROE", "NIM"]


@dataclass
class GMMRunConfig:
    input_path: Path
    sheet_name: str
    id_col: str
    time_col: str
    dep: str
    mode: str
    predetermined: List[str]
    strict_iv: List[str]
    dep_lags: int
    gmm_y_lags: str
    gmm_pred_lags: str
    min_periods: int
    collapse: bool
    onestep: bool
    timedumm: bool
    fod: bool
    output_dir: Path


def parse_var_list(text: Optional[str], default: List[str]) -> List[str]:
    """Converte lista separada por vírgulas em lista Python, preservando default quando None."""
    if text is None:
        return list(default)
    text = text.strip()
    if not text:
        return []
    return [x.strip() for x in text.split(",") if x.strip()]


def keep_existing(cols: Iterable[str], df: pd.DataFrame) -> List[str]:
    """Mantém apenas colunas existentes, sem duplicidade."""
    out = []
    seen = set()
    for c in cols:
        if c in df.columns and c not in seen:
            out.append(c)
            seen.add(c)
    return out


def has_within_variation(df: pd.DataFrame, var: str, id_col: str) -> bool:
    """Retorna True se houver alguma variação temporal dentro de ao menos uma unidade do painel."""
    nunique_by_id = df.groupby(id_col, observed=True)[var].nunique(dropna=True)
    return bool((nunique_by_id > 1).any())


def is_constant_by_time(df: pd.DataFrame, var: str, time_col: str) -> bool:
    """Retorna True se a variável é igual para todas as entidades dentro de cada período."""
    nunique_by_t = df.groupby(time_col, observed=True)[var].nunique(dropna=True)
    return bool((nunique_by_t <= 1).all())


def dependency_check() -> None:
    if regression is None:
        raise SystemExit(
            "ERRO: pacote pydynpd não encontrado. Instale as dependências antes de executar:\n"
            "    pip install pandas numpy openpyxl scipy prettytable pydynpd\n"
            f"Detalhe técnico: {PYDYNPD_IMPORT_ERROR}"
        )


def load_and_prepare_base(cfg: GMMRunConfig) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """Lê a base, cria identificadores numéricos para o painel e aplica limpeza inicial."""
    if not cfg.input_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {cfg.input_path}")

    df = pd.read_excel(cfg.input_path, sheet_name=cfg.sheet_name)
    df.columns = [str(c).strip() for c in df.columns]

    required = [cfg.id_col, cfg.time_col, cfg.dep]
    missing_required = [c for c in required if c not in df.columns]
    if missing_required:
        raise ValueError(f"Colunas obrigatórias ausentes: {missing_required}. Colunas disponíveis: {list(df.columns)}")

    # Identificadores internos numéricos para maior compatibilidade com pydynpd.
    df = df.copy()
    df[cfg.id_col] = df[cfg.id_col].astype(str).str.strip()

    # Ordena os períodos originais e cria um índice temporal sequencial comum a todas as entidades.
    # Isso evita problemas com datas trimestrais no formato AAAAMM, que não têm incremento aritmético constante.
    ordered_periods = sorted(df[cfg.time_col].dropna().unique())
    time_map = {period: idx + 1 for idx, period in enumerate(ordered_periods)}
    id_map = {entity: idx + 1 for idx, entity in enumerate(sorted(df[cfg.id_col].dropna().unique()))}

    df["id_gmm"] = df[cfg.id_col].map(id_map).astype("Int64")
    df["time_gmm"] = df[cfg.time_col].map(time_map).astype("Int64")

    # Converte variáveis numéricas relevantes.
    candidate_numeric = set(DEFAULT_DEPENDENTS + DEFAULT_PREDETERMINED + DEFAULT_STRICT_IV + cfg.predetermined + cfg.strict_iv)
    candidate_numeric = [c for c in candidate_numeric if c in df.columns]
    for c in candidate_numeric:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.sort_values(["id_gmm", "time_gmm"]).reset_index(drop=True)

    meta = {
        "n_rows_original": int(len(df)),
        "n_entities_original": int(df["id_gmm"].nunique(dropna=True)),
        "n_periods_original": int(df["time_gmm"].nunique(dropna=True)),
        "time_map": {str(k): int(v) for k, v in time_map.items()},
        "id_map": {str(k): int(v) for k, v in id_map.items()},
    }
    return df, meta


def select_model_variables(df: pd.DataFrame, cfg: GMMRunConfig) -> Tuple[List[str], List[str], List[str], List[str]]:
    """Seleciona variáveis disponíveis e remove variáveis inadequadas para cada modo."""
    pred = keep_existing(cfg.predetermined, df)
    iv = keep_existing(cfg.strict_iv, df)

    # Remove dependente de regressores/instrumentos adicionais, caso tenha sido incluída por engano.
    pred = [v for v in pred if v != cfg.dep]
    iv = [v for v in iv if v != cfg.dep]

    notes = []

    # Remove variáveis constantes no recorte da amostra.
    usable = [cfg.dep] + pred + iv + ["id_gmm", "time_gmm"]
    work = df[usable].copy()
    work = work.dropna(subset=[cfg.dep, "id_gmm", "time_gmm"])

    # Remover variáveis integralmente ausentes ou sem variação.
    for var in list(pred):
        if work[var].dropna().nunique() <= 1:
            pred.remove(var)
            notes.append(f"Removida de predeterminadas por ausência de variação: {var}")
    for var in list(iv):
        if work[var].dropna().nunique() <= 1:
            iv.remove(var)
            notes.append(f"Removida de IV por ausência de variação: {var}")

    # Difference GMM elimina efeitos fixos por diferenciação; variáveis invariantes dentro da entidade
    # não são identificadas na equação em diferenças.
    if cfg.mode == "difference":
        for var in list(pred):
            if not has_within_variation(work, var, "id_gmm"):
                pred.remove(var)
                notes.append(f"Removida do Difference GMM por não variar dentro da instituição: {var}")
        for var in list(iv):
            if not has_within_variation(work, var, "id_gmm"):
                iv.remove(var)
                notes.append(f"Removida do Difference GMM por não variar dentro da instituição: {var}")

    # Dummies temporais absorvem variáveis comuns a todas as entidades em cada período.
    if cfg.timedumm:
        for var in list(pred):
            if is_constant_by_time(work, var, "time_gmm"):
                pred.remove(var)
                notes.append(f"Removida por colinearidade potencial com dummies temporais: {var}")
        for var in list(iv):
            if is_constant_by_time(work, var, "time_gmm"):
                iv.remove(var)
                notes.append(f"Removida por colinearidade potencial com dummies temporais: {var}")

    # Monta amostra final com as variáveis efetivamente usadas.
    regressors = pred + iv
    required = [cfg.dep, "id_gmm", "time_gmm"] + regressors
    required = list(dict.fromkeys(required))
    work = df[required].dropna().copy()

    # Mantém apenas grupos com número mínimo de períodos depois da remoção de missing values.
    counts = work.groupby("id_gmm", observed=True)["time_gmm"].nunique()
    valid_ids = counts[counts >= cfg.min_periods].index
    work = work[work["id_gmm"].isin(valid_ids)].copy()
    work = work.sort_values(["id_gmm", "time_gmm"]).reset_index(drop=True)

    if work.empty:
        raise ValueError("A amostra final ficou vazia após drop de missing values e filtro de períodos mínimos.")

    return work, pred, iv, notes


def dep_lag_expression(dep: str, dep_lags: int) -> str:
    if dep_lags < 1:
        raise ValueError("dep_lags deve ser >= 1.")
    if dep_lags == 1:
        return f"L1.{dep}"
    return f"L(1:{dep_lags}).{dep}"


def build_pydynpd_command(cfg: GMMRunConfig, pred: List[str], iv: List[str]) -> str:
    """Cria a string de comando do pydynpd."""
    regressors = pred + iv
    part1 = " ".join([cfg.dep, dep_lag_expression(cfg.dep, cfg.dep_lags)] + regressors)

    inst_parts = [f"gmm({cfg.dep}, {cfg.gmm_y_lags})"]
    if pred:
        inst_parts.append(f"gmm({' '.join(pred)}, {cfg.gmm_pred_lags})")
    if iv:
        inst_parts.append(f"iv({' '.join(iv)})")
    part2 = " ".join(inst_parts)

    options = []
    if cfg.mode == "difference":
        options.append("nolevel")
    if cfg.onestep:
        options.append("onestep")
    if cfg.collapse:
        options.append("collapse")
    if cfg.timedumm:
        options.append("timedumm")
    if cfg.fod:
        options.append("fod")
    part3 = " ".join(options)

    return f"{part1} | {part2} | {part3}".strip()


def model_diagnostics(model, dep: str, mode: str, command: str) -> Dict[str, object]:
    """Extrai diagnósticos principais do objeto pydynpd."""
    ar1 = model.AR_list[0] if hasattr(model, "AR_list") and len(model.AR_list) > 0 else None
    ar2 = model.AR_list[1] if hasattr(model, "AR_list") and len(model.AR_list) > 1 else None
    hansen = getattr(model, "hansen", None)
    z_list = getattr(model, "z_list", None)

    n_instruments = None
    if z_list is not None:
        try:
            n_instruments = int(z_list.shape[1])
        except Exception:
            n_instruments = None

    n_groups = getattr(model, "N", None)
    warning_msgs = []
    if n_instruments is not None and n_groups is not None and n_instruments >= n_groups:
        warning_msgs.append("Número de instrumentos >= número de grupos; avalie reduzir defasagens/usar collapse.")
    if hansen is not None:
        hp = getattr(hansen, "p_value", None)
        if hp is not None:
            if hp < 0.05:
                warning_msgs.append("Hansen rejeita a validade conjunta dos instrumentos ao nível de 5%.")
            elif hp > 0.99:
                warning_msgs.append("Hansen muito alto; pode indicar proliferação/excesso de instrumentos.")
    if ar2 is not None:
        ar2p = getattr(ar2, "P_value", None)
        if ar2p is not None and ar2p < 0.05:
            warning_msgs.append("AR(2) significativo; instrumentos baseados em defasagens podem ser inválidos.")

    return {
        "dependent": dep,
        "mode": mode,
        "command": command,
        "n_obs": getattr(model, "num_obs", None),
        "n_groups": n_groups,
        "n_periods": getattr(model, "T", None),
        "min_obs_per_group": getattr(model, "min_obs", None),
        "avg_obs_per_group": getattr(model, "avg_obs", None),
        "max_obs_per_group": getattr(model, "max_obs", None),
        "n_instruments": n_instruments,
        "hansen_chi2": getattr(hansen, "test_value", None) if hansen is not None else None,
        "hansen_df": getattr(hansen, "df", None) if hansen is not None else None,
        "hansen_p": getattr(hansen, "p_value", None) if hansen is not None else None,
        "ar1_z": getattr(ar1, "AR", None) if ar1 is not None else None,
        "ar1_p": getattr(ar1, "P_value", None) if ar1 is not None else None,
        "ar2_z": getattr(ar2, "AR", None) if ar2 is not None else None,
        "ar2_p": getattr(ar2, "P_value", None) if ar2 is not None else None,
        "warnings": " | ".join(warning_msgs),
    }


def run_single_model(df_raw: pd.DataFrame, cfg: GMMRunConfig, meta: Dict[str, object]) -> Dict[str, object]:
    """Prepara amostra, estima um modo GMM e salva saídas."""
    work, pred, iv, notes = select_model_variables(df_raw, cfg)
    command = build_pydynpd_command(cfg, pred, iv)

    # pydynpd usa os nomes passados em identifiers. Mantemos apenas colunas necessárias.
    model_cols = ["id_gmm", "time_gmm", cfg.dep] + pred + iv
    model_cols = list(dict.fromkeys(model_cols))
    data_for_model = work[model_cols].copy()

    stdout_buffer = io.StringIO()
    with contextlib.redirect_stdout(stdout_buffer):
        result = regression.abond(command, data_for_model, ["id_gmm", "time_gmm"])
    console_output = stdout_buffer.getvalue()

    if not hasattr(result, "models") or len(result.models) == 0:
        raise RuntimeError(f"pydynpd não retornou modelos para: {command}")

    # Quando não há '?' no comando, normalmente há apenas um modelo. Ainda assim salvamos todos, se houver.
    coefficient_tables = []
    diagnostics = []
    for idx, model in enumerate(result.models):
        tbl = model.regression_table.copy()
        tbl.insert(0, "model_index", idx)
        tbl.insert(1, "dependent", cfg.dep)
        tbl.insert(2, "mode", cfg.mode)
        coefficient_tables.append(tbl)
        diagnostics.append(model_diagnostics(model, cfg.dep, cfg.mode, model.command_str if hasattr(model, "command_str") else command))

    coef_df = pd.concat(coefficient_tables, ignore_index=True)
    diag_df = pd.DataFrame(diagnostics)

    sample_summary = {
        "dependent": cfg.dep,
        "mode": cfg.mode,
        "n_rows_after_cleaning": int(len(data_for_model)),
        "n_entities_after_cleaning": int(data_for_model["id_gmm"].nunique()),
        "n_periods_after_cleaning": int(data_for_model["time_gmm"].nunique()),
        "predetermined_used": pred,
        "strict_iv_used": iv,
        "notes": notes,
        "command": command,
    }

    return {
        "coef": coef_df,
        "diag": diag_df,
        "sample": sample_summary,
        "console": console_output,
        "command": command,
        "data_for_model": data_for_model,
        "meta": meta,
    }


def save_outputs(results: List[Dict[str, object]], cfg_base: GMMRunConfig) -> Path:
    """Salva resultados em CSV, TXT, JSON e XLSX."""
    outdir = cfg_base.output_dir
    outdir.mkdir(parents=True, exist_ok=True)

    all_coef = pd.concat([r["coef"] for r in results], ignore_index=True)
    all_diag = pd.concat([r["diag"] for r in results], ignore_index=True)
    sample_info = [r["sample"] for r in results]
    commands = [r["command"] for r in results]

    all_coef.to_csv(outdir / "gmm_coeficientes.csv", index=False, encoding="utf-8-sig")
    all_diag.to_csv(outdir / "gmm_diagnosticos.csv", index=False, encoding="utf-8-sig")
    with open(outdir / "gmm_comandos.txt", "w", encoding="utf-8") as f:
        f.write("\n\n".join(commands))
    with open(outdir / "gmm_sample_info.json", "w", encoding="utf-8") as f:
        json.dump(sample_info, f, ensure_ascii=False, indent=2)
    with open(outdir / "gmm_console_output.txt", "w", encoding="utf-8") as f:
        for r in results:
            f.write("=" * 100 + "\n")
            f.write(r["command"] + "\n")
            f.write("=" * 100 + "\n")
            f.write(r["console"] + "\n")

    xlsx_path = outdir / "gmm_resultados.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        all_coef.to_excel(writer, sheet_name="coeficientes", index=False)
        all_diag.to_excel(writer, sheet_name="diagnosticos", index=False)
        pd.DataFrame(sample_info).to_excel(writer, sheet_name="amostra_modelo", index=False)
        pd.DataFrame({"command": commands}).to_excel(writer, sheet_name="comandos", index=False)

    return xlsx_path


def build_configs(args: argparse.Namespace, dep: str, mode: str) -> GMMRunConfig:
    predetermined = parse_var_list(args.predetermined, DEFAULT_PREDETERMINED)
    strict_iv = parse_var_list(args.strict_iv, DEFAULT_STRICT_IV)
    return GMMRunConfig(
        input_path=Path(args.input),
        sheet_name=args.sheet,
        id_col=args.id_col,
        time_col=args.time_col,
        dep=dep,
        mode=mode,
        predetermined=predetermined,
        strict_iv=strict_iv,
        dep_lags=args.dep_lags,
        gmm_y_lags=args.gmm_y_lags,
        gmm_pred_lags=args.gmm_pred_lags,
        min_periods=args.min_periods,
        collapse=not args.no_collapse,
        onestep=args.onestep,
        timedumm=args.timedumm,
        fod=args.fod,
        output_dir=Path(args.output_dir),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Estima Difference GMM e/ou System GMM em painel dinâmico usando pydynpd."
    )
    parser.add_argument("--input", default="base_final.xlsx", help="Arquivo .xlsx de entrada.")
    parser.add_argument("--sheet", default="base", help="Nome da aba da planilha.")
    parser.add_argument("--id-col", default="id_entidade", help="Coluna identificadora da instituição.")
    parser.add_argument("--time-col", default="AnoMes_ord", help="Coluna temporal original.")
    parser.add_argument(
        "--dep",
        default="ROA",
        help="Variável dependente: ROA, ROE, NIM ou all para estimar as três.",
    )
    parser.add_argument(
        "--mode",
        default="both",
        choices=["difference", "system", "both"],
        help="Modelo a estimar: difference, system ou both.",
    )
    parser.add_argument(
        "--predetermined",
        default=None,
        help="Lista separada por vírgulas de variáveis predeterminadas/endógenas fracas. Se omitido, usa default do script.",
    )
    parser.add_argument(
        "--strict-iv",
        default=None,
        help="Lista separada por vírgulas de variáveis tratadas como estritamente exógenas. Se omitido, usa default do script.",
    )
    parser.add_argument("--dep-lags", type=int, default=1, help="Número máximo de defasagens da dependente no lado direito.")
    parser.add_argument("--gmm-y-lags", default="2:3", help="Defasagens de instrumentos GMM para a dependente. Ex.: 2:3, 2:4, 2:.")
    parser.add_argument("--gmm-pred-lags", default="1:2", help="Defasagens de instrumentos GMM para variáveis predeterminadas. Ex.: 1:2")
    parser.add_argument("--min-periods", type=int, default=5, help="Mínimo de períodos por instituição após limpeza.")
    parser.add_argument("--no-collapse", action="store_true", help="Não colapsar matriz de instrumentos.")
    parser.add_argument("--onestep", action="store_true", help="Usar one-step GMM. Default é two-step robusto do pydynpd.")
    parser.add_argument("--timedumm", action="store_true", help="Incluir dummies temporais automaticamente.")
    parser.add_argument("--fod", action="store_true", help="Usar forward orthogonal deviations em vez de primeira diferença.")
    parser.add_argument("--output-dir", default="gmm_outputs", help="Pasta de saída.")
    return parser.parse_args()


def main() -> None:
    warnings.simplefilter("once", category=RuntimeWarning)
    args = parse_args()
    dependency_check()

    deps = DEFAULT_DEPENDENTS if args.dep.lower() == "all" else [args.dep]
    modes = ["difference", "system"] if args.mode == "both" else [args.mode]

    # Leitura única da base com uma configuração inicial.
    cfg0 = build_configs(args, dep=deps[0], mode=modes[0])
    df_raw, meta = load_and_prepare_base(cfg0)

    results = []
    for dep in deps:
        if dep not in df_raw.columns:
            print(f"[AVISO] Dependente ignorada porque não existe na base: {dep}", file=sys.stderr)
            continue
        for mode in modes:
            cfg = build_configs(args, dep=dep, mode=mode)
            print(f"\nEstimando {mode.upper()} GMM para {dep}...")
            result = run_single_model(df_raw, cfg, meta)
            results.append(result)
            print(result["diag"].to_string(index=False))

    if not results:
        raise SystemExit("Nenhum modelo foi estimado. Verifique --dep, --mode e nomes de colunas.")

    xlsx_path = save_outputs(results, cfg0)
    print("\nConcluído.")
    print(f"Resultados salvos em: {xlsx_path.resolve()}")
    print(f"Coeficientes CSV: {(cfg0.output_dir / 'gmm_coeficientes.csv').resolve()}")
    print(f"Diagnósticos CSV: {(cfg0.output_dir / 'gmm_diagnosticos.csv').resolve()}")


if __name__ == "__main__":
    main()
