#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sanity check entre base consolidada (.xlsx) e arquivos IFData em JSONL.

Objetivo
--------
Comparar somente as colunas da base consolidada que têm origem no IFData,
validando se os valores da base.xlsx correspondem aos saldos originais do IFData.

Entradas esperadas
------------------
1) base.xlsx: base em formato wide, com uma linha por instituição/período.
2) ifdata_*.jsonl: IFData em formato longo, com colunas como:
   CodInst, AnoMes, NomeColuna e Saldo.

Saídas
------
- sanity_check_ifdata_detalhado.csv: comparação por linha/coluna.
- sanity_check_ifdata_resumo_colunas.csv: resumo por coluna testada.
- sanity_check_ifdata_resumo_geral.json: métricas gerais do sanity check.
- sanity_check_ifdata_colunas_mapeadas.csv: mapeamento NomeColuna IFData -> coluna da base.
- sanity_check_ifdata_colunas_sem_match_na_base.csv: colunas IFData reconhecidas, mas ausentes na base.
- sanity_check_ifdata_keys_nao_encontradas.csv: chaves da base sem contraparte no IFData.

python 12_3_sanity_check_ifdata.py --base bases/base.xlsx --ifdata ifdata/rel_4/ifdata_valores_201503_tipo1_rel4.jsonl --sheet dados --out-dir outputs/sanity_ifdata_rel_4
"""

from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd


# -----------------------------------------------------------------------------
# 1. Mapeamento IFData -> colunas esperadas na base consolidada
# -----------------------------------------------------------------------------
# O script compara apenas as colunas reconhecidas como originadas do IFData.
# A associação é feita por prefixo normalizado de NomeColuna, para tolerar
# quebras de linha, acentos e sufixos como "(a)", "(i) = ..." etc.
IFDATA_PREFIX_TO_EXPECTED_BASE_COL = {
    "ativos_ponderados_pelo_risco_rwa": "ativos_ponderados_pelo_risco",
    "capital_complementar": "capital_complementar",
    "capital_nivel_ii": "capital_nivel_ii",
    "capital_principal_para_comparacao_com_rwa": "capital_principal_para_comparacao_com_RWA",
    "patrimonio_de_referencia_nivel_i_para_comparacao_com_rwa": "patrimonio_de_referencia_nivel_i_para_comparacao_com_RWA",
    "patrimonio_de_referencia_para_comparacao_com_o_rwa": "patrimonio_de_referencia_para_comparacao_com_o_RWA",
    "rwa_para_risco_operacional": "RWA_para_risco_operacional",
    "rwa_para_risco_de_credito": "RWA_para_risco_de_credito",
    "rwa_para_risco_de_mercado": "RWA_para_risco_de_mercado",
    "rwacam": "RWAcam",
    "rwacom": "RWAcom",
    "rwajur": "RWAjur",
    "rwaacs": "RWAacs",
    "exposicao_total": "exposicao_total",
    "indice_de_basileia": "indice_de_basileia",
    "indice_de_capital_principal": "indice_de_capital_principal",
    "indice_de_capital_nivel_i": "indice_de_capital_nivel_i",
    "indice_de_imobilizacao": "indice_de_imobilizacao",
    "razao_de_alavancagem": "razao_de_alavancagem",
    # Relatório 2 — Ativo
    "ativo_total_ajustado": "ativo_total_ajustado",
    "ativo_total": "ativo_total",
    "disponibilidades": "disponibilidades",
    "aplicacoes_interfinanceiras_de_liquidez": "aplicacoes_interfinanceiras_de_liquidez",
    "tvm_e_instrumentos_financeiros_derivativos": "tvm_e_instrumentos_financeiros_derivativos",
    "operacoes_de_credito_liquidas_de_provisao": "operacoes_de_credito_liquidas_de_provisao",
    "operacoes_de_credito": "operacoes_de_credito",
    "provisao_sobre_operacoes_de_credito": "provisao_sobre_operacoes_de_credito",
    "arrendamento_mercantil_liquido_de_provisao": "arrendamento_mercantil_liquido_de_provisao",
    "arrendamento_mercantil_a_receber": "arrendamento_mercantil_a_receber",
    "imobilizado_de_arrendamento": "imobilizado_de_arrendamento",
    "credores_por_antecipacao_de_valor_residual": "credores_por_antecipacao_de_valor_residual",
    "provisao_sobre_arrendamento_mercantil": "provisao_sobre_arrendamento_mercantil",
    "outros_creditos_liquido_de_provisao": "outros_creditos_liquido_de_provisao",
    "outros_ativos_realizaveis": "outros_ativos_realizaveis",
    "permanente_ajustado": "permanente_ajustado",
    # Relatório 3 — Passivo
    "patrimonio_liquido": "patrimonio_liquido",
    "instrumentos_derivativos": "instrumentos_derivativos",
    "outras_obrigacoes": "outras_obrigacoes",
    "passivo_circulante_e_exigivel_a_longo_prazo": "passivo_circulante_e_exigivel_a_longo_prazo",
    "resultados_de_exercicios_futuros": "resultados_de_exercicios_futuros",
    "passivo_total": "passivo_total",
    "captacoes": "captacoes",
    "obrigacoes_por_operacoes_compromissadas": "obrigacoes_por_operacoes_compromissadas",
    "obrigacoes_por_emprestimos_e_repasses": "obrigacoes_por_emprestimos_e_repasses",
    "depositos_a_vista": "depositos_a_vista",
    "depositos_de_poupanca": "depositos_de_poupanca",
    "depositos_interfinanceiros": "depositos_interfinanceiros",
    "outros_depositos": "outros_depositos",
    "depositos_a_prazo": "depositos_a_prazo",
    "deposito_total": "depositos",
    "letras_de_credito_imobiliario": "letras_de_credito_imobiliario",
    "letras_de_credito_do_agronegocio": "letras_de_credito_do_agronegocio",
    "letras_financeiras": "letras_financeiras",
    "obrigacoes_por_titulos_e_valores_mobiliarios_no_exterior": "obrigacoes_por_titulos_e_valores_mobiliarios_no_exterior",
    "outros_recursos_de_aceites_e_emissao_de_titulos": "outros_recursos_de_aceites_e_emissao_de_titulos",
    "recursos_de_aceites_e_emissao_de_titulos": "recursos_de_aceites_e_emissao_de_titulos",
    # Relatório 4 — Demonstração de Resultado
    "lucro_liquido": "lucro_liquido",
    "resultado_operacional": "resultado_operacional",
    "resultado_antes_da_tributacao_lucro_e_participacao": "resultado_antes_da_tributacao_lucro_e_participacao",
    "resultado_nao_operacional": "resultado_nao_operacional",
    "imposto_de_renda_e_contribuicao_social": "imposto_de_renda_e_contribuicao_social",
    "participacao_nos_lucros": "participacao_nos_lucros",
    "juros_sobre_capital_proprio": "juros_sobre_capital_proprio",

    "receitas_de_intermediacao_financeira": "receitas_de_intermediacao_financeira",
    "rendas_de_operacoes_de_credito": "rendas_de_operacoes_de_credito",
    "rendas_de_operacoes_de_arrendamento_mercantil": "rendas_de_operacoes_de_arrendamento_mercantil",
    "rendas_de_operacoes_com_tvm": "rendas_de_operacoes_com_TVM",
    "rendas_de_operacoes_com_instrumentos_financeiros_derivativos": "rendas_de_operacoes_com_instrumentos_financeiros_derivativos",
    "rendas_de_aplicacoes_compulsorias": "rendas_de_aplicacoes_compulsorias",

    "despesas_de_intermediacao_financeira": "despesas_de_intermediacao_financeira",
    "despesas_de_captacao": "despesas_de_captacao",
    "despesas_de_obrigacoes_por_emprestimos_e_repasses": "despesas_de_obrigacoes_por_emprestimos_e_repasses",
    "despesas_de_operacoes_de_arrendamento_mercantil": "despesas_de_operacoes_de_arrendamento_mercantil",
    "resultado_de_provisao_para_creditos_de_dificil_liquidacao": "resultado_de_provisao_para_creditos_de_dificil_liquidacao",

    "resultado_de_intermediacao_financeira": "resultado_de_intermediacao_financeira",
    "outras_receitas_despesas_operacionais": "outras_receitas_despesas_operacionais",
    "rendas_de_prestacao_de_servicos": "rendas_de_prestacao_de_servicos",
    "rendas_de_tarifas_bancarias": "rendas_de_tarifas_bancarias",
    "despesas_de_pessoal": "despesas_de_pessoal",
    "despesas_administrativas": "despesas_administrativas",
    "despesas_tributarias": "despesas_tributarias",
    "resultado_de_participacoes": "resultado_de_participacoes",
    "outras_receitas_operacionais": "outras_receitas_operacionais",
    "outras_despesas_operacionais": "outras_despesas",
}

# Mapeamento mínimo útil para os arquivos anexados nesta rodada.
# Edite ou sobrescreva via --entity-map / --mapping quando usar outros bancos.
DEFAULT_ENTITY_MAP = {
    # Mapeamento mínimo para os tickers/códigos presentes no base.xlsx anexado.
    # Quando houver uma tabela oficial de correspondência, prefira informar via --mapping.
    "ABCB4": "C0080312",
    "BAZA3": "C0081249",
    "BBAS3": "C0080329",
    "BBDC4": "C0080075",
    "BEES4": "C0080147",
    "BGIP4": "C0081634",
    "BNBR3": "C0081593",
    "BRSR6": "C0080154",
    "BSLI4": "C0080288",
    "PINE4": "C0080374",
    "RPAD6": "C0080109",
    "SANB11": "C0080185",
    "C0080123": "C0080123",
    "C0080336": "C0080336",
}


# -----------------------------------------------------------------------------
# 2. Funções auxiliares de normalização e leitura
# -----------------------------------------------------------------------------
def normalize_text(value: object) -> str:
    """Normaliza nomes de colunas: sem acento, minúsculo e snake_case."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    text = str(value).strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text

def canonical_ifdata_column(nome_coluna: object) -> Optional[str]:
    """Retorna o nome esperado da coluna na base para um NomeColuna do IFData."""
    norm = normalize_text(nome_coluna)

    # Usa o prefixo mais específico primeiro.
    # Isso evita colisões como:
    # "ativo_total" vs. "ativo_total_ajustado"
    # "operacoes_de_credito" vs. "operacoes_de_credito_liquidas_de_provisao"
    for prefix, expected_col in sorted(
        IFDATA_PREFIX_TO_EXPECTED_BASE_COL.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if norm.startswith(prefix):
            return expected_col

    return None


def build_normalized_column_lookup(columns: Iterable[object]) -> Dict[str, str]:
    """Mapeia nome normalizado -> nome real da coluna no DataFrame."""
    lookup: Dict[str, str] = {}
    for col in columns:
        norm = normalize_text(col)
        # Mantém a primeira ocorrência. Isso evita ambiguidades em colunas duplicadas.
        if norm and norm not in lookup:
            lookup[norm] = col
    return lookup


def find_anomes_col(df: pd.DataFrame, requested: str = "AnoMes") -> str:
    """
    Localiza a coluna de período no formato YYYYMM.

    A base anexada tem a primeira coluna com cabeçalho numérico, embora os valores
    sejam AnoMes. Por isso, se 'AnoMes' não existir, detectamos automaticamente
    uma coluna com alta proporção de valores no padrão YYYYMM.
    """
    if requested in df.columns:
        return requested

    requested_norm = normalize_text(requested)
    for col in df.columns:
        if normalize_text(col) == requested_norm:
            return col

    candidates: List[Tuple[float, str]] = []
    for col in df.columns:
        s = df[col].dropna().astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
        if s.empty:
            continue
        is_yyyymm = s.str.match(r"^(19|20)\d{2}(0[1-9]|1[0-2])$")
        ratio = float(is_yyyymm.mean())
        if ratio >= 0.70:
            candidates.append((ratio, col))

    if not candidates:
        raise ValueError(
            "Não foi possível localizar a coluna de AnoMes na base. "
            "Informe explicitamente com --base-anomes-col."
        )

    candidates.sort(reverse=True, key=lambda x: x[0])
    return candidates[0][1]


def clean_anomes(series: pd.Series) -> pd.Series:
    """Padroniza AnoMes como string YYYYMM."""
    return (
        series.astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
        .str.zfill(6)
    )


def read_ifdata_jsonl(paths: List[Path]) -> pd.DataFrame:
    """Lê um ou mais arquivos JSONL do IFData."""
    frames = []
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Arquivo IFData não encontrado: {path}")
        df = pd.read_json(path, lines=True, dtype={"CodInst": str, "AnoMes": str})
        df["arquivo_origem"] = path.name
        frames.append(df)
    if not frames:
        raise ValueError("Nenhum arquivo IFData informado.")
    out = pd.concat(frames, ignore_index=True)
    required = {"CodInst", "AnoMes", "NomeColuna", "Saldo"}
    missing = required - set(out.columns)
    if missing:
        raise ValueError(f"O IFData não contém as colunas obrigatórias: {sorted(missing)}")
    out["AnoMes"] = clean_anomes(out["AnoMes"])
    out["CodInst"] = out["CodInst"].astype(str).str.strip()
    out["Saldo"] = pd.to_numeric(out["Saldo"], errors="coerce")
    return out


def load_entity_map(args: argparse.Namespace) -> Dict[str, str]:
    """Carrega mapeamento id_entidade -> CodInst a partir do padrão, CSV e CLI."""
    entity_map: Dict[str, str] = dict(DEFAULT_ENTITY_MAP)

    if args.no_default_entity_map:
        entity_map = {}

    if args.mapping:
        mapping_path = Path(args.mapping)
        mapping_df = pd.read_csv(mapping_path, dtype=str)
        required = {args.mapping_base_col, args.mapping_codinst_col}
        missing = required - set(mapping_df.columns)
        if missing:
            raise ValueError(
                f"Arquivo de mapping sem colunas obrigatórias {sorted(missing)}. "
                f"Colunas encontradas: {list(mapping_df.columns)}"
            )
        for _, row in mapping_df.iterrows():
            base_id = str(row[args.mapping_base_col]).strip()
            codinst = str(row[args.mapping_codinst_col]).strip()
            if base_id and codinst and base_id.lower() != "nan" and codinst.lower() != "nan":
                entity_map[base_id] = codinst

    for pair in args.entity_map or []:
        if "=" not in pair:
            raise ValueError(f"Formato inválido em --entity-map: {pair}. Use ID_BASE=CODINST.")
        base_id, codinst = pair.split("=", 1)
        entity_map[base_id.strip()] = codinst.strip()

    return entity_map


# -----------------------------------------------------------------------------
# 3. Preparação das bases para comparação
# -----------------------------------------------------------------------------
def prepare_ifdata_wide(ifdata: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Converte IFData longo para wide no nível (AnoMes, CodInst).

    Retorna:
    - wide: saldos pivotados por coluna reconhecida.
    - mapped_cols: pares NomeColuna -> expected_base_col.
    - duplicates: duplicidades/conflictos no IFData já mapeado.
    """
    df = ifdata.copy()
    df["expected_base_col"] = df["NomeColuna"].apply(canonical_ifdata_column)
    df = df[df["expected_base_col"].notna()].copy()

    mapped_cols = (
        df[["NomeColuna", "expected_base_col", "Grupo", "Conta"]]
        .drop_duplicates()
        .sort_values(["expected_base_col", "NomeColuna"])
    )

    # Diagnóstico de duplicidades por chave/coluna. Duplicidade com mesmo valor é menos grave,
    # mas ainda é útil reportar para rastreabilidade.
    dup_diag = (
        df.groupby(["AnoMes", "CodInst", "expected_base_col"], dropna=False)
        .agg(
            n_linhas=("Saldo", "size"),
            n_valores_distintos=("Saldo", lambda s: s.dropna().round(10).nunique()),
            saldos_distintos=("Saldo", lambda s: "; ".join(map(str, sorted(s.dropna().round(10).unique())[:5]))),
        )
        .reset_index()
    )
    duplicates = dup_diag[dup_diag["n_linhas"] > 1].copy()

    wide = (
        df.pivot_table(
            index=["AnoMes", "CodInst"],
            columns="expected_base_col",
            values="Saldo",
            aggfunc="first",
        )
        .reset_index()
    )
    wide.columns.name = None
    return wide, mapped_cols, duplicates


def prepare_base(
    base_path: Path,
    sheet: str,
    base_entity_col: str,
    base_anomes_col: str,
    expected_cols: List[str],
    entity_map: Dict[str, str],
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, str], str]:
    """
    Lê a base consolidada e mantém apenas as colunas testáveis.

    Retorna:
    - base_cmp: base pronta para merge, com AnoMes e CodInst.
    - base_raw: base original lida.
    - expected_to_actual: mapeamento nome esperado -> nome real na base.
    - anomes_col_detected: coluna de período detectada.
    """
    base_raw = pd.read_excel(base_path, sheet_name=sheet)
    anomes_col = find_anomes_col(base_raw, base_anomes_col)

    if base_entity_col not in base_raw.columns:
        # tenta localizar por nome normalizado
        lookup = build_normalized_column_lookup(base_raw.columns)
        found = lookup.get(normalize_text(base_entity_col))
        if found is None:
            raise ValueError(
                f"Coluna de entidade '{base_entity_col}' não encontrada na base. "
                f"Colunas disponíveis: {list(base_raw.columns)}"
            )
        base_entity_col = found

    col_lookup = build_normalized_column_lookup(base_raw.columns)
    expected_to_actual: Dict[str, str] = {}
    for expected in expected_cols:
        actual = col_lookup.get(normalize_text(expected))
        if actual is not None:
            expected_to_actual[expected] = actual

    keep_actual_cols = [anomes_col, base_entity_col] + list(expected_to_actual.values())
    base_cmp = base_raw[keep_actual_cols].copy()
    base_cmp = base_cmp.rename(columns={anomes_col: "AnoMes", base_entity_col: "id_entidade"})
    # Renomeia as colunas reais da base para os nomes esperados/canônicos.
    rename_actual_to_expected = {actual: expected for expected, actual in expected_to_actual.items()}
    base_cmp = base_cmp.rename(columns=rename_actual_to_expected)

    base_cmp["AnoMes"] = clean_anomes(base_cmp["AnoMes"])
    base_cmp["id_entidade"] = base_cmp["id_entidade"].astype(str).str.strip()
    base_cmp["CodInst"] = base_cmp["id_entidade"].map(entity_map)

    # Caso a base já use CodInst como id_entidade, permite comparação direta.
    missing_map_mask = base_cmp["CodInst"].isna() & base_cmp["id_entidade"].isin(entity_map.values())
    base_cmp.loc[missing_map_mask, "CodInst"] = base_cmp.loc[missing_map_mask, "id_entidade"]

    for col in expected_to_actual.keys():
        base_cmp[col] = pd.to_numeric(base_cmp[col], errors="coerce")

    return base_cmp, base_raw, expected_to_actual, anomes_col


def infer_missing_entity_map(
    base_cmp: pd.DataFrame,
    ifdata_wide: pd.DataFrame,
    cols_to_compare: List[str],
    atol: float,
    rtol: float,
    min_matches: int = 3,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Infere CodInst para id_entidade sem mapeamento, usando coincidência de valores.

    Essa inferência é útil quando não há arquivo de mapping. Ela é reportada em CSV,
    pois deve ser revisada pelo pesquisador antes de ser tratada como definitiva.
    """
    inferred_rows = []
    out = base_cmp.copy()
    missing_entities = sorted(out.loc[out["CodInst"].isna(), "id_entidade"].dropna().unique())
    if not missing_entities or not cols_to_compare:
        return out, pd.DataFrame(columns=["id_entidade", "CodInst_inferido", "matches", "comparacoes", "erro_abs_medio"])

    candidate_codes = sorted(ifdata_wide["CodInst"].dropna().unique())

    for entity in missing_entities:
        entity_base = out[out["id_entidade"] == entity][["AnoMes"] + cols_to_compare].copy()
        best = None
        for cod in candidate_codes:
            cand = ifdata_wide[ifdata_wide["CodInst"] == cod][["AnoMes"] + cols_to_compare].copy()
            merged = entity_base.merge(cand, on="AnoMes", suffixes=("_base", "_ifdata"))
            if merged.empty:
                continue
            total = 0
            matches = 0
            diffs = []
            for col in cols_to_compare:
                b = pd.to_numeric(merged[f"{col}_base"], errors="coerce")
                i = pd.to_numeric(merged[f"{col}_ifdata"], errors="coerce")
                valid = b.notna() & i.notna()
                if not valid.any():
                    continue
                diff_abs = (b[valid] - i[valid]).abs()
                ok = diff_abs <= (atol + rtol * i[valid].abs())
                total += int(valid.sum())
                matches += int(ok.sum())
                diffs.extend(diff_abs.tolist())
            if total == 0:
                continue
            mae = float(np.mean(diffs)) if diffs else np.inf
            score = (matches, -mae, total)
            if best is None or score > best[0]:
                best = (score, cod, matches, total, mae)

        if best is not None and best[2] >= min_matches:
            _, cod, matches, total, mae = best
            out.loc[out["id_entidade"] == entity, "CodInst"] = cod
            inferred_rows.append(
                {
                    "id_entidade": entity,
                    "CodInst_inferido": cod,
                    "matches": matches,
                    "comparacoes": total,
                    "erro_abs_medio": mae,
                }
            )

    return out, pd.DataFrame(inferred_rows)


# -----------------------------------------------------------------------------
# 4. Comparação e geração dos relatórios
# -----------------------------------------------------------------------------
def classify_row(base_val: float, ifdata_val: float, diff_abs: float, tolerance: float) -> str:
    if pd.isna(base_val) and pd.isna(ifdata_val):
        return "OK_AMBOS_NULOS"
    if pd.isna(base_val) and not pd.isna(ifdata_val):
        return "AUSENTE_NA_BASE"
    if not pd.isna(base_val) and pd.isna(ifdata_val):
        return "AUSENTE_NO_IFDATA"
    if diff_abs <= tolerance:
        return "OK"
    return "DIVERGENTE"


def compare_base_ifdata(
    base_cmp: pd.DataFrame,
    ifdata_wide: pd.DataFrame,
    cols_to_compare: List[str],
    atol: float,
    rtol: float,
    strict_keys: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Compara valores da base contra os saldos pivotados do IFData.

    Por padrão, o detalhamento compara apenas chaves existentes nos dois lados
    (AnoMes, CodInst). Isso evita contar como erro períodos da base que não foram
    fornecidos nos arquivos IFData anexados. Use --strict-keys para tratar chaves
    sem IFData como AUSENTE_NO_IFDATA.
    """
    merge_cols = ["AnoMes", "CodInst"]
    base_keys = base_cmp[["AnoMes", "id_entidade", "CodInst"] + cols_to_compare].copy()

    merged = base_keys.merge(
        ifdata_wide[merge_cols + cols_to_compare],
        on=merge_cols,
        how="left",
        suffixes=("_base", "_ifdata"),
        indicator=True,
    )

    key_misses = merged[merged["_merge"] == "left_only"][["AnoMes", "id_entidade", "CodInst"]].drop_duplicates()

    # Se strict_keys=False, compara apenas as chaves que existem nos dois lados.
    # As chaves ausentes continuam reportadas em sanity_check_ifdata_keys_nao_encontradas.csv.
    merged_for_values = merged if strict_keys else merged[merged["_merge"] == "both"].copy()

    detail_rows = []
    for col in cols_to_compare:
        b = pd.to_numeric(merged_for_values[f"{col}_base"], errors="coerce")
        i = pd.to_numeric(merged_for_values[f"{col}_ifdata"], errors="coerce")
        diff_abs = (b - i).abs()
        denom = i.abs().replace(0, np.nan)
        diff_rel = diff_abs / denom
        tolerance = atol + rtol * i.abs().fillna(0)

        tmp = pd.DataFrame(
            {
                "AnoMes": merged_for_values["AnoMes"],
                "id_entidade": merged_for_values["id_entidade"],
                "CodInst": merged_for_values["CodInst"],
                "coluna_base": col,
                "valor_base": b,
                "valor_ifdata": i,
                "diff_abs": diff_abs,
                "diff_rel": diff_rel,
                "tolerancia_aplicada": tolerance,
            }
        )
        tmp["status"] = [
            classify_row(bv, iv, da, tol)
            for bv, iv, da, tol in zip(tmp["valor_base"], tmp["valor_ifdata"], tmp["diff_abs"], tmp["tolerancia_aplicada"])
        ]
        detail_rows.append(tmp)

    detailed = pd.concat(detail_rows, ignore_index=True) if detail_rows else pd.DataFrame()

    summary = (
        detailed.groupby("coluna_base", dropna=False)
        .agg(
            n_comparacoes=("status", "size"),
            n_ok=("status", lambda s: int(s.isin(["OK", "OK_AMBOS_NULOS"]).sum())),
            n_divergente=("status", lambda s: int((s == "DIVERGENTE").sum())),
            n_ausente_base=("status", lambda s: int((s == "AUSENTE_NA_BASE").sum())),
            n_ausente_ifdata=("status", lambda s: int((s == "AUSENTE_NO_IFDATA").sum())),
            max_diff_abs=("diff_abs", "max"),
            media_diff_abs=("diff_abs", "mean"),
            max_diff_rel=("diff_rel", "max"),
        )
        .reset_index()
    )
    summary["pct_ok"] = np.where(
        summary["n_comparacoes"] > 0,
        summary["n_ok"] / summary["n_comparacoes"],
        np.nan,
    )
    return detailed, summary, key_misses


def write_outputs(
    out_dir: Path,
    detailed: pd.DataFrame,
    summary: pd.DataFrame,
    mapped_cols: pd.DataFrame,
    cols_without_base_match: pd.DataFrame,
    key_misses: pd.DataFrame,
    duplicate_ifdata: pd.DataFrame,
    inferred_map: pd.DataFrame,
    metadata: dict,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    detailed.to_csv(out_dir / "sanity_check_ifdata_detalhado.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(out_dir / "sanity_check_ifdata_resumo_colunas.csv", index=False, encoding="utf-8-sig")
    mapped_cols.to_csv(out_dir / "sanity_check_ifdata_colunas_mapeadas.csv", index=False, encoding="utf-8-sig")
    cols_without_base_match.to_csv(out_dir / "sanity_check_ifdata_colunas_sem_match_na_base.csv", index=False, encoding="utf-8-sig")
    key_misses.to_csv(out_dir / "sanity_check_ifdata_keys_nao_encontradas.csv", index=False, encoding="utf-8-sig")
    duplicate_ifdata.to_csv(out_dir / "sanity_check_ifdata_duplicidades_ifdata.csv", index=False, encoding="utf-8-sig")
    inferred_map.to_csv(out_dir / "sanity_check_ifdata_mapeamento_inferido.csv", index=False, encoding="utf-8-sig")

    with open(out_dir / "sanity_check_ifdata_resumo_geral.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # Conveniência: gera também um XLSX com as abas principais, caso openpyxl esteja disponível.
    try:
        with pd.ExcelWriter(out_dir / "sanity_check_ifdata_relatorio.xlsx", engine="openpyxl") as writer:
            summary.to_excel(writer, sheet_name="resumo_colunas", index=False)
            detailed.to_excel(writer, sheet_name="detalhado", index=False)
            key_misses.to_excel(writer, sheet_name="keys_sem_ifdata", index=False)
            mapped_cols.to_excel(writer, sheet_name="mapeamento_colunas", index=False)
            cols_without_base_match.to_excel(writer, sheet_name="cols_sem_match_base", index=False)
            duplicate_ifdata.to_excel(writer, sheet_name="duplicidades_ifdata", index=False)
            inferred_map.to_excel(writer, sheet_name="mapa_inferido", index=False)
    except Exception as exc:  # pragma: no cover - apenas fallback de conveniência
        print(f"[AVISO] Não foi possível gerar o XLSX consolidado: {exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sanity check entre colunas IFData da base consolidada e JSONL original do IFData."
    )
    parser.add_argument("--base", required=True, help="Caminho para base.xlsx")
    parser.add_argument(
        "--ifdata",
        required=True,
        nargs="+",
        help="Um ou mais arquivos IFData .jsonl em formato longo",
    )
    parser.add_argument("--sheet", default="dados", help="Aba da base.xlsx a ser analisada. Padrão: dados")
    parser.add_argument("--out-dir", default="sanity_ifdata", help="Diretório de saída dos relatórios")
    parser.add_argument("--base-entity-col", default="id_entidade", help="Coluna de entidade na base.xlsx")
    parser.add_argument("--base-anomes-col", default="AnoMes", help="Coluna de período na base.xlsx")
    parser.add_argument(
        "--entity-map",
        action="append",
        default=[],
        help="Mapeamento ID_BASE=CODINST. Pode ser repetido. Ex.: --entity-map ABCB4=C0080312",
    )
    parser.add_argument("--mapping", default=None, help="CSV opcional com mapeamento id_entidade -> CodInst")
    parser.add_argument("--mapping-base-col", default="id_entidade", help="Coluna do CSV de mapping com o ID da base")
    parser.add_argument("--mapping-codinst-col", default="CodInst", help="Coluna do CSV de mapping com CodInst")
    parser.add_argument(
        "--no-default-entity-map",
        action="store_true",
        help="Ignora o mapeamento padrão mínimo embutido no script.",
    )
    parser.add_argument(
        "--infer-missing-map",
        action="store_true",
        help="Tenta inferir CodInst para entidades sem mapping usando coincidência de valores.",
    )
    parser.add_argument("--atol", type=float, default=1e-6, help="Tolerância absoluta. Padrão: 1e-6")
    parser.add_argument("--rtol", type=float, default=1e-9, help="Tolerância relativa. Padrão: 1e-9")
    parser.add_argument(
        "--strict-keys",
        action="store_true",
        help=(
            "Inclui no detalhamento linhas da base sem chave correspondente no IFData. "
            "Sem esta opção, essas chaves são apenas reportadas em arquivo separado."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_path = Path(args.base)
    ifdata_paths = [Path(p) for p in args.ifdata]
    out_dir = Path(args.out_dir)

    if not base_path.exists():
        raise FileNotFoundError(f"Base não encontrada: {base_path}")

    entity_map = load_entity_map(args)

    print("[INFO] Lendo IFData...")
    ifdata = read_ifdata_jsonl(ifdata_paths)
    ifdata_wide, mapped_cols, duplicate_ifdata = prepare_ifdata_wide(ifdata)

    expected_cols = sorted([c for c in ifdata_wide.columns if c not in {"AnoMes", "CodInst"}])
    print(f"[INFO] Colunas IFData reconhecidas: {len(expected_cols)}")

    print("[INFO] Lendo base consolidada...")
    base_cmp, base_raw, expected_to_actual, anomes_col_detected = prepare_base(
        base_path=base_path,
        sheet=args.sheet,
        base_entity_col=args.base_entity_col,
        base_anomes_col=args.base_anomes_col,
        expected_cols=expected_cols,
        entity_map=entity_map,
    )

    cols_to_compare = [c for c in expected_cols if c in expected_to_actual]
    cols_without_base_match = pd.DataFrame(
        [
            {"expected_base_col": c, "motivo": "Coluna reconhecida no IFData, mas não localizada na base.xlsx"}
            for c in expected_cols
            if c not in expected_to_actual
        ]
    )

    if not cols_to_compare:
        raise ValueError(
            "Nenhuma coluna IFData reconhecida foi encontrada na base.xlsx. "
            "Verifique nomes das colunas ou atualize IFDATA_PREFIX_TO_EXPECTED_BASE_COL."
        )

    if args.infer_missing_map:
        print("[INFO] Inferindo CodInst para entidades sem mapping...")
        base_cmp, inferred_map = infer_missing_entity_map(
            base_cmp=base_cmp,
            ifdata_wide=ifdata_wide,
            cols_to_compare=cols_to_compare,
            atol=args.atol,
            rtol=args.rtol,
        )
    else:
        inferred_map = pd.DataFrame(
            columns=["id_entidade", "CodInst_inferido", "matches", "comparacoes", "erro_abs_medio"]
        )

    # Mantém no teste apenas linhas da base para as quais há CodInst definido.
    base_unmapped = base_cmp[base_cmp["CodInst"].isna()][["AnoMes", "id_entidade"]].drop_duplicates()
    base_cmp_mapped = base_cmp[base_cmp["CodInst"].notna()].copy()

    print(f"[INFO] Colunas que serão comparadas: {len(cols_to_compare)}")
    for col in cols_to_compare:
        print(f"       - {col}")

    print("[INFO] Comparando valores...")
    detailed, summary, key_misses = compare_base_ifdata(
        base_cmp=base_cmp_mapped,
        ifdata_wide=ifdata_wide,
        cols_to_compare=cols_to_compare,
        atol=args.atol,
        rtol=args.rtol,
        strict_keys=args.strict_keys,
    )

    if not base_unmapped.empty:
        base_unmapped = base_unmapped.assign(CodInst=np.nan, motivo="id_entidade sem mapeamento para CodInst")
        key_misses = pd.concat([key_misses, base_unmapped], ignore_index=True, sort=False)

    n_total = int(len(detailed))
    n_ok = int(detailed["status"].isin(["OK", "OK_AMBOS_NULOS"]).sum()) if n_total else 0
    n_div = int((detailed["status"] == "DIVERGENTE").sum()) if n_total else 0
    n_abs_base = int((detailed["status"] == "AUSENTE_NA_BASE").sum()) if n_total else 0
    n_abs_ifdata = int((detailed["status"] == "AUSENTE_NO_IFDATA").sum()) if n_total else 0

    metadata = {
        "base": str(base_path),
        "sheet": args.sheet,
        "ifdata": [str(p) for p in ifdata_paths],
        "out_dir": str(out_dir),
        "coluna_anomes_detectada_na_base": str(anomes_col_detected),
        "colunas_ifdata_reconhecidas": int(len(expected_cols)),
        "colunas_comparadas": cols_to_compare,
        "n_linhas_base": int(len(base_raw)),
        "n_linhas_base_com_codinst_mapeado": int(len(base_cmp_mapped)),
        "n_linhas_ifdata": int(len(ifdata)),
        "n_chaves_base_sem_ifdata": int(len(key_misses)),
        "n_comparacoes": n_total,
        "n_ok": n_ok,
        "n_divergente": n_div,
        "n_ausente_na_base": n_abs_base,
        "n_ausente_no_ifdata": n_abs_ifdata,
        "pct_ok": float(n_ok / n_total) if n_total else None,
        "atol": args.atol,
        "rtol": args.rtol,
        "observacao": (
            "O teste compara apenas colunas reconhecidas como originadas do IFData e presentes na base. "
            "Colunas IFData não encontradas na base são listadas em sanity_check_ifdata_colunas_sem_match_na_base.csv."
        ),
    }

    print("[INFO] Gravando relatórios...")
    write_outputs(
        out_dir=out_dir,
        detailed=detailed,
        summary=summary,
        mapped_cols=mapped_cols,
        cols_without_base_match=cols_without_base_match,
        key_misses=key_misses,
        duplicate_ifdata=duplicate_ifdata,
        inferred_map=inferred_map,
        metadata=metadata,
    )

    print("\n[OK] Sanity check concluído.")
    print(f"     Diretório de saída: {out_dir}")
    print(f"     Comparações: {n_total}")
    print(f"     OK: {n_ok}")
    print(f"     Divergentes: {n_div}")
    print(f"     Ausentes na base: {n_abs_base}")
    print(f"     Ausentes no IFData: {n_abs_ifdata}")
    print(f"     % OK: {metadata['pct_ok']:.4%}" if metadata["pct_ok"] is not None else "     % OK: n/a")

    return 0 if n_div == 0 and n_abs_base == 0 and n_abs_ifdata == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
