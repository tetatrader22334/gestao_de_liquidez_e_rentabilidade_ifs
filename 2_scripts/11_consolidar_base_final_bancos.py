
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# ======================================================================================
# Mapeamento fornecido pelo usuário (com aliases para os tickers que aparecem no statements)
# ======================================================================================

# python consolidar_base_final_bancos.py --ifdata bases/base_consolidada_ifdata_wide.xlsx --statements bases/statements.csv --macro bases/macro.csv -o bases/base_final_bancos

ENTITY_MAP = [
    {
        "ticker_input": "RPAD5",
        "nome": "Alfa Holding",
        "cod_conglomerado": "C0010083",
        "cod_prudencial": "C0080109",
        "cnpj_lider": "3323840",
    },
    {
        "ticker_input": "BEES4",
        "nome": "Banestes",
        "cod_conglomerado": "C0030159",
        "cod_prudencial": "C0080147",
        "cnpj_lider": "C0030159",
    },
    {
        "ticker_input": "ABCB4",
        "nome": "ABC Brasil",
        "cod_conglomerado": "C0041856",
        "cod_prudencial": "C0080312",
        "cnpj_lider": "28195667",
    },
    {
        "ticker_input": "BAZA3",
        "nome": "Banco Amazônia",
        "cod_conglomerado": None,
        "cod_prudencial": "C0081249",
        "cnpj_lider": "4902979",
    },
    {
        "ticker_input": "BBDC4",
        "nome": "Bradesco",
        "cod_conglomerado": "C0010045",
        "cod_prudencial": "C0080075",
        "cnpj_lider": "60746948",
    },
    {
        "ticker_input": "BBAS3",
        "nome": "Banco do Brasil",
        "cod_conglomerado": "C0049906",
        "cod_prudencial": "C0080329",
        "cnpj_lider": "0",
    },
    {
        "ticker_input": "BPAC11",
        "nome": "BTG Pactual",
        "cod_conglomerado": "C0049944",
        "cod_prudencial": "C0080336",
        "cnpj_lider": "30306294",
    },
    {
        "ticker_input": "BGIP4",
        "nome": "Banco do estado de Sergipe",
        "cod_conglomerado": None,
        "cod_prudencial": "C0081634",
        "cnpj_lider": "13009717",
    },
    {
        "ticker_input": "BRSR5",
        "nome": "Banrisul",
        "cod_conglomerado": "C0030173",
        "cod_prudencial": "C0080154",
        "cnpj_lider": "92702067",
    },
    {
        "ticker_input": "BMIN4",
        "nome": "Banco mercantil de investimentos",
        "cod_conglomerado": "C0020152",
        "cod_prudencial": "C0080123",
        "cnpj_lider": "34169557",
    },
    {
        "ticker_input": "BMEB4",
        "nome": "Banco mercantil do Brasil",
        "cod_conglomerado": "C0020152",
        "cod_prudencial": "C0080123",
        "cnpj_lider": "17184037",
    },
    {
        "ticker_input": "BNBR3",
        "nome": "Banco do Nordeste",
        "cod_conglomerado": None,
        "cod_prudencial": "C0081593",
        "cnpj_lider": "7237373",
    },
    {
        "ticker_input": "BPAN4",
        "nome": "Banco Pan",
        "cod_conglomerado": "C0049944",
        "cod_prudencial": "C0080336",
        "cnpj_lider": "59285411",
    },
    {
        "ticker_input": "PINE10",
        "nome": "Banco Pine",
        "cod_conglomerado": "C0050304",
        "cod_prudencial": "C0080374",
        "cnpj_lider": "62144175",
    },
    {
        "ticker_input": "SANB11",
        "nome": "Santander Brasil",
        "cod_conglomerado": "C0030379",
        "cod_prudencial": "C0080185",
        "cnpj_lider": "90400888",
    },
    {
        "ticker_input": "BSLI4",
        "nome": "BRB Banco de Brasília",
        "cod_conglomerado": "C0031976",
        "cod_prudencial": "C0080288",
        "cnpj_lider": "208",
    },
]

# Tickers que aparecem no statements.csv em lugar do ticker fornecido no mapeamento
TICKER_ALIAS_TO_STATEMENTS = {
    "RPAD5": "RPAD6",
    "BRSR5": "BRSR6",
    "PINE10": "PINE4",
}

IFDATA_DETAIL_META_COLS = {
    "NomeRelatorio",
    "NumeroRelatorio",
    "Grupo",
    "AnoMes_arquivo",
    "RelatorioArquivo",
    "ArquivoOrigem",
    "TipoArquivo",
}


def _clean_str(x: Any) -> str | None:
    if pd.isna(x) or x is None:
        return None
    s = str(x).strip()
    return s if s and s != "--" else None


def _sanitize_column(name: str) -> str:
    s = str(name).replace("\n", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if suffix == ".csv":
        last_error = None
        for sep in [",", ";", "\t", "|"]:
            try:
                df = pd.read_csv(path, sep=sep)
                if df.shape[1] > 1:
                    return df
            except Exception as e:
                last_error = e
        raise ValueError(f"Não foi possível ler CSV {path}. Último erro: {last_error}")
    if suffix == ".parquet":
        return pd.read_parquet(path)

    raise ValueError(f"Extensão não suportada: {suffix}")


def _prudential_codes_from_map() -> set[str]:
    return {
        str(rec["cod_prudencial"]).strip()
        for rec in ENTITY_MAP
        if rec.get("cod_prudencial") not in (None, "", "--")
    }


def _conglomerate_codes_from_map() -> set[str]:
    return {
        str(rec["cod_conglomerado"]).strip()
        for rec in ENTITY_MAP
        if rec.get("cod_conglomerado") not in (None, "", "--")
    }


def infer_ifdata_regime_from_codinst(codinst_series: pd.Series) -> pd.Series:
    prudential_codes = _prudential_codes_from_map()
    conglomerate_codes = _conglomerate_codes_from_map()

    def _infer_one(x: Any) -> str | None:
        s = _clean_str(x)
        if s is None:
            return None
        if s in prudential_codes:
            return "prudencial"
        if s in conglomerate_codes:
            return "conglomerado"
        # fallback heurístico: nos arquivos do usuário, códigos prudenciais aparecem como C008....
        if s.upper().startswith("C008"):
            return "prudencial"
        if re.match(r"^C00[1-7]\d{4}$", s.upper()):
            return "conglomerado"
        return None

    return codinst_series.map(_infer_one).astype("string")


def build_entity_dimension(statements_df: pd.DataFrame) -> pd.DataFrame:
    dim = pd.DataFrame(ENTITY_MAP).copy()

    for col in ["ticker_input", "nome", "cod_conglomerado", "cod_prudencial", "cnpj_lider"]:
        dim[col] = dim[col].map(_clean_str)

    dim["ticker_statements"] = dim["ticker_input"].replace(TICKER_ALIAS_TO_STATEMENTS)
    dim["ticker_canonico"] = dim["ticker_statements"]

    tickers_statements = set(statements_df["Ticker"].dropna().astype(str).str.strip().unique())
    dim["ticker_encontrado_statements"] = dim["ticker_statements"].isin(tickers_statements)

    counts_cod = (
        dim.dropna(subset=["cod_prudencial"])
        .groupby("cod_prudencial")["ticker_canonico"]
        .nunique()
        .rename("n_tickers_por_cod_prudencial")
        .reset_index()
    )
    dim = dim.merge(counts_cod, on="cod_prudencial", how="left")
    dim["n_tickers_por_cod_prudencial"] = dim["n_tickers_por_cod_prudencial"].fillna(0).astype(int)
    dim["flag_alias"] = dim["ticker_input"] != dim["ticker_statements"]
    dim["flag_ambiguidade_cod_prudencial"] = dim["n_tickers_por_cod_prudencial"] > 1

    dim["status_merge"] = np.select(
        [
            ~dim["ticker_encontrado_statements"],
            dim["flag_ambiguidade_cod_prudencial"],
            dim["flag_alias"],
        ],
        [
            "sem_statements",
            "ambiguo_cod_prudencial",
            "alias",
        ],
        default="ok",
    )

    dim["id_entidade"] = dim["ticker_canonico"]

    return dim.sort_values(["status_merge", "ticker_canonico"]).reset_index(drop=True)


def filter_statements_quarterly(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [_sanitize_column(c) for c in out.columns]
    out["Ticker"] = out["Ticker"].astype(str).str.strip()
    out["Ticker"] = out["Ticker"].replace(TICKER_ALIAS_TO_STATEMENTS)
    out["AnoMes"] = pd.to_numeric(out["AnoMes"], errors="coerce").astype("Int64")

    if "TipoPeriodo" in out.columns:
        tp = out["TipoPeriodo"].astype("string").str.strip().str.lower()
        mask = tp.isna() | (tp == "quarterly")
        out = out.loc[mask].copy()

    dup = out.duplicated(["Ticker", "AnoMes"]).sum()
    if dup:
        raise ValueError(f"statements possui {dup} duplicidades em Ticker + AnoMes após normalização.")

    return out.reset_index(drop=True)


def _collapse_ifdata_panel_form(
    out: pd.DataFrame,
    regime: str = "prudencial",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Trata IFData já no formato painel (uma linha por CodInst + AnoMes),
    como a base anexada pelo usuário.
    """
    id_cols = [c for c in ["TipoInstituicao", "CodInst", "AnoMes"] if c in out.columns]
    out["regime_inferido"] = infer_ifdata_regime_from_codinst(out["CodInst"])

    if regime != "todos":
        out = out.loc[out["regime_inferido"] == regime].copy()

    if out.empty:
        raise ValueError(
            f"Nenhuma linha restou no IFData após aplicar regime='{regime}' "
            "sobre a base já consolidada."
        )

    ignore_cols = {"regime_inferido"}
    measure_cols = [c for c in out.columns if c not in set(id_cols) | ignore_cols]

    for c in measure_cols:
        out[c] = pd.to_numeric(out[c], errors="coerce")

    nunique_per_group = out.groupby(id_cols, dropna=False)[measure_cols].nunique(dropna=True)
    conflict_mask = nunique_per_group.gt(1)
    rows_with_conflict = conflict_mask.any(axis=1)
    conflict_summary = []

    if rows_with_conflict.any():
        conflict_groups = nunique_per_group.loc[rows_with_conflict]
        for idx, row in conflict_groups.iterrows():
            conflicting_vars = row[row > 1].index.tolist()
            if isinstance(idx, tuple):
                rec = {id_cols[i]: idx[i] for i in range(len(id_cols))}
            else:
                rec = {id_cols[0]: idx}
            rec["variaveis_em_conflito"] = ", ".join(conflicting_vars)
            conflict_summary.append(rec)

    conflicts_df = pd.DataFrame(conflict_summary)

    if not conflicts_df.empty:
        raise ValueError(
            "Foram detectados conflitos no IFData já consolidado em CodInst + AnoMes. "
            "Consulte o relatório de conflitos."
        )

    collapsed = (
        out.groupby(id_cols, dropna=False)[measure_cols]
        .first()
        .reset_index()
        .sort_values([c for c in ["CodInst", "AnoMes"] if c in out.columns])
        .reset_index(drop=True)
    )

    collapsed["regime_ifdata"] = infer_ifdata_regime_from_codinst(collapsed["CodInst"])
    return collapsed, conflicts_df


def _collapse_ifdata_detailed_form(
    out: pd.DataFrame,
    regime: str = "prudencial",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Trata IFData em forma detalhada, com colunas como TipoArquivo, Grupo, Relatório etc.
    """
    out["regime_inferido"] = infer_ifdata_regime_from_codinst(out["CodInst"])

    if "TipoArquivo" in out.columns:
        out["TipoArquivo"] = pd.to_numeric(out["TipoArquivo"], errors="coerce").astype("Int64")
        regime_from_tipo = np.select(
            [out["TipoArquivo"] == 1, out["TipoArquivo"] == 2],
            ["prudencial", "conglomerado"],
            default=pd.NA,
        )
        out["regime_ifdata_linha"] = pd.Series(regime_from_tipo, index=out.index, dtype="string")
        mask_missing = out["regime_ifdata_linha"].isna()
        out.loc[mask_missing, "regime_ifdata_linha"] = out.loc[mask_missing, "regime_inferido"]
    else:
        out["regime_ifdata_linha"] = out["regime_inferido"]

    if regime != "todos":
        out = out.loc[out["regime_ifdata_linha"] == regime].copy()

    if out.empty:
        raise ValueError(
            f"Nenhuma linha restou no IFData após aplicar regime='{regime}'."
        )

    id_cols = [c for c in ["TipoInstituicao", "CodInst", "AnoMes"] if c in out.columns]
    ignore_cols = set(IFDATA_DETAIL_META_COLS) | {"regime_inferido", "regime_ifdata_linha"}
    measure_cols = [c for c in out.columns if c not in set(id_cols) | ignore_cols]

    for c in measure_cols:
        out[c] = pd.to_numeric(out[c], errors="coerce")

    nunique_per_group = out.groupby(id_cols, dropna=False)[measure_cols].nunique(dropna=True)
    conflict_mask = nunique_per_group.gt(1)
    rows_with_conflict = conflict_mask.any(axis=1)
    conflict_summary = []

    if rows_with_conflict.any():
        conflict_groups = nunique_per_group.loc[rows_with_conflict]
        for idx, row in conflict_groups.iterrows():
            conflicting_vars = row[row > 1].index.tolist()
            if isinstance(idx, tuple):
                rec = {id_cols[i]: idx[i] for i in range(len(id_cols))}
            else:
                rec = {id_cols[0]: idx}
            rec["variaveis_em_conflito"] = ", ".join(conflicting_vars)
            conflict_summary.append(rec)

    conflicts_df = pd.DataFrame(conflict_summary)

    if not conflicts_df.empty:
        raise ValueError(
            "Foram detectados conflitos no IFData ao colapsar para CodInst + AnoMes. "
            "Consulte o relatório de conflitos."
        )

    collapsed = (
        out.groupby(id_cols, dropna=False)[measure_cols]
        .first()
        .reset_index()
        .sort_values([c for c in ["CodInst", "AnoMes"] if c in out.columns])
        .reset_index(drop=True)
    )

    collapsed["regime_ifdata"] = infer_ifdata_regime_from_codinst(collapsed["CodInst"])
    return collapsed, conflicts_df


def collapse_ifdata_to_inst_quarter(
    df: pd.DataFrame,
    regime: str = "prudencial",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Aceita duas formas de IFData:
    1) forma detalhada, com TipoArquivo / Grupo / Relatório / ArquivoOrigem
    2) forma já consolidada, com uma linha por CodInst + AnoMes, como no anexo do usuário

    Retorna:
    - base no nível CodInst + AnoMes
    - relatório de conflitos
    """
    out = df.copy()
    out.columns = [_sanitize_column(c) for c in out.columns]

    if "CodInst" not in out.columns or "AnoMes" not in out.columns:
        raise ValueError("IFData precisa conter, no mínimo, as colunas CodInst e AnoMes.")

    out["CodInst"] = out["CodInst"].astype(str).str.strip()
    out["AnoMes"] = pd.to_numeric(out["AnoMes"], errors="coerce").astype("Int64")

    # Se já não há colunas de detalhamento e a base parece painel, trata como painel.
    has_detail_cols = any(c in out.columns for c in IFDATA_DETAIL_META_COLS)
    dup_codinst_anomes = out.duplicated(["CodInst", "AnoMes"]).sum()

    if (not has_detail_cols) and dup_codinst_anomes == 0:
        return _collapse_ifdata_panel_form(out, regime=regime)

    return _collapse_ifdata_detailed_form(out, regime=regime)


def quarter_end_anomes_from_date(date_series: pd.Series) -> pd.Series:
    d = pd.to_datetime(date_series, errors="coerce")
    months = pd.Series(np.select(
        [d.dt.quarter == 1, d.dt.quarter == 2, d.dt.quarter == 3, d.dt.quarter == 4],
        [3, 6, 9, 12],
        default=np.nan,
    ), index=d.index)
    return (d.dt.year * 100 + months).astype("Int64")


def aggregate_macro_to_quarter(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [_sanitize_column(c) for c in out.columns]

    if "date" not in out.columns:
        raise ValueError("macro.csv precisa conter a coluna date.")

    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.loc[out["date"].notna()].copy()

    out["AnoMes"] = quarter_end_anomes_from_date(out["date"])
    out["ano"] = out["date"].dt.year
    out["trimestre"] = out["date"].dt.quarter

    if "ipca" in out.columns:
        out["ipca"] = pd.to_numeric(out["ipca"], errors="coerce")
    if "selic" in out.columns:
        out["selic"] = pd.to_numeric(out["selic"], errors="coerce")
    if "pib_trimestral_sa" in out.columns:
        out["pib_trimestral_sa"] = pd.to_numeric(out["pib_trimestral_sa"], errors="coerce")

    agg_dict = {}
    if "ipca" in out.columns:
        agg_dict.update({
            "ipca_media_trimestre": ("ipca", "mean"),
            "ipca_soma_trimestre": ("ipca", "sum"),
            "ipca_fim_trimestre": ("ipca", "last"),
        })
    if "selic" in out.columns:
        agg_dict.update({
            "selic_media_trimestre": ("selic", "mean"),
            "selic_fim_trimestre": ("selic", "last"),
        })
    if "pib_trimestral_sa" in out.columns:
        agg_dict.update({
            "pib_trimestral_sa": ("pib_trimestral_sa", lambda s: s.dropna().iloc[0] if s.dropna().size else np.nan),
        })

    grouped = out.groupby(["AnoMes", "ano", "trimestre"], dropna=False).agg(**agg_dict).reset_index()
    grouped = grouped.sort_values("AnoMes").reset_index(drop=True)
    return grouped


def merge_all(
    ifdata_path: str | Path,
    statements_path: str | Path,
    macro_path: str | Path,
    out_prefix: str | Path,
    regime: str = "prudencial",
    excluir_ambiguos: bool = True,
) -> dict[str, Any]:
    ifdata_raw = _read_table(ifdata_path)
    statements_raw = _read_table(statements_path)
    macro_raw = _read_table(macro_path)

    statements_q = filter_statements_quarterly(statements_raw)
    dim = build_entity_dimension(statements_q)
    ifdata_panel, ifdata_conflicts = collapse_ifdata_to_inst_quarter(ifdata_raw, regime=regime)
    macro_q = aggregate_macro_to_quarter(macro_raw)

    if excluir_ambiguos:
        dim_usable = dim.loc[~dim["flag_ambiguidade_cod_prudencial"] & dim["ticker_encontrado_statements"]].copy()
    else:
        dim_usable = dim.loc[dim["ticker_encontrado_statements"]].copy()

    base = ifdata_panel.merge(
        dim_usable,
        left_on="CodInst",
        right_on="cod_prudencial",
        how="left",
        validate="many_to_one",
    )

    base["flag_sem_mapeamento_dim"] = base["ticker_canonico"].isna()

    statements_usable = statements_q.merge(
        dim_usable[["ticker_canonico"]].drop_duplicates(),
        left_on="Ticker",
        right_on="ticker_canonico",
        how="inner",
        validate="many_to_one",
    ).drop(columns=["ticker_canonico"])

    merged = base.merge(
        statements_usable,
        left_on=["ticker_canonico", "AnoMes"],
        right_on=["Ticker", "AnoMes"],
        how="left",
        validate="many_to_one",
        suffixes=("", "_st"),
    )

    merged["flag_sem_statements"] = merged["Ticker"].isna()

    merged = merged.merge(
        macro_q,
        on="AnoMes",
        how="left",
        validate="many_to_one",
    )
    merged["flag_sem_macro"] = merged["ano"].isna()

    preferred_order = [c for c in [
        "id_entidade",
        "ticker_canonico",
        "nome",
        "cod_prudencial",
        "cod_conglomerado",
        "cnpj_lider",
        "CodInst",
        "TipoInstituicao",
        "AnoMes",
        "regime_ifdata",
        "status_merge",
        "flag_alias",
        "flag_ambiguidade_cod_prudencial",
        "flag_sem_mapeamento_dim",
        "flag_sem_statements",
        "flag_sem_macro",
    ] if c in merged.columns]

    other_cols = [c for c in merged.columns if c not in preferred_order]
    merged = merged[preferred_order + other_cols].sort_values(
        [c for c in ["id_entidade", "AnoMes"] if c in merged.columns]
    ).reset_index(drop=True)

    dim_full = dim.copy()
    ambiguous_entities = dim_full.loc[dim_full["flag_ambiguidade_cod_prudencial"]].copy()
    unmatched_ifdata_codes = sorted(set(ifdata_panel["CodInst"].unique()) - set(dim_usable["cod_prudencial"].dropna().unique()))
    matched_entities = sorted(merged.loc[merged["flag_sem_statements"] == False, "id_entidade"].dropna().unique().tolist())

    stats = {
        "linhas_ifdata_raw": int(len(ifdata_raw)),
        "linhas_ifdata_panel": int(len(ifdata_panel)),
        "codigos_ifdata_panel": int(ifdata_panel["CodInst"].nunique()),
        "periodo_ifdata_min": int(ifdata_panel["AnoMes"].min()) if len(ifdata_panel) else None,
        "periodo_ifdata_max": int(ifdata_panel["AnoMes"].max()) if len(ifdata_panel) else None,
        "linhas_statements_raw": int(len(statements_raw)),
        "linhas_statements_quarterly": int(len(statements_q)),
        "tickers_statements_quarterly": int(statements_q["Ticker"].nunique()),
        "linhas_macro_raw": int(len(macro_raw)),
        "linhas_macro_quarterly": int(len(macro_q)),
        "entidades_dim_total": int(len(dim)),
        "entidades_dim_usaveis": int(len(dim_usable)),
        "entidades_ambiguas_excluidas": int(ambiguous_entities["ticker_canonico"].nunique()) if excluir_ambiguos else 0,
        "codigos_prudenciais_ambiguos_excluidos": sorted(ambiguous_entities["cod_prudencial"].dropna().unique().tolist()) if excluir_ambiguos else [],
        "linhas_base_final": int(len(merged)),
        "entidades_base_final": int(merged["id_entidade"].nunique(dropna=True)),
        "entidades_com_statements": int(merged.loc[~merged["flag_sem_statements"], "id_entidade"].nunique(dropna=True)),
        "entidades_listadas_com_statements": matched_entities,
        "linhas_sem_statements": int(merged["flag_sem_statements"].sum()),
        "linhas_sem_macro": int(merged["flag_sem_macro"].sum()),
        "linhas_sem_mapeamento_dim": int(merged["flag_sem_mapeamento_dim"].sum()),
        "codigos_ifdata_sem_mapeamento": unmatched_ifdata_codes,
    }

    out_prefix = Path(out_prefix)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    merged_csv = out_prefix.with_suffix(".csv")
    merged_xlsx = out_prefix.with_suffix(".xlsx")
    dim_csv = out_prefix.with_name(out_prefix.stem + "_dimensao_entidades.csv")
    macro_csv = out_prefix.with_name(out_prefix.stem + "_macro_trimestral.csv")
    stats_json = out_prefix.with_name(out_prefix.stem + "_diagnosticos.json")
    ambiguity_csv = out_prefix.with_name(out_prefix.stem + "_ambiguidades.csv")
    conflicts_csv = out_prefix.with_name(out_prefix.stem + "_ifdata_conflitos.csv")

    merged.to_csv(merged_csv, index=False, encoding="utf-8-sig")
    merged.to_excel(merged_xlsx, index=False)
    dim_full.to_csv(dim_csv, index=False, encoding="utf-8-sig")
    macro_q.to_csv(macro_csv, index=False, encoding="utf-8-sig")
    ambiguous_entities.to_csv(ambiguity_csv, index=False, encoding="utf-8-sig")
    ifdata_conflicts.to_csv(conflicts_csv, index=False, encoding="utf-8-sig")
    stats_json.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "merged_csv": str(merged_csv),
        "merged_xlsx": str(merged_xlsx),
        "dim_csv": str(dim_csv),
        "macro_csv": str(macro_csv),
        "ambiguity_csv": str(ambiguity_csv),
        "conflicts_csv": str(conflicts_csv),
        "stats_json": str(stats_json),
        "stats": stats,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Consolida IFData + statements + macro em uma única base trimestral no nível entidade-regulatória × trimestre. "
            "Aceita IFData tanto na forma detalhada quanto já consolidada em CodInst + AnoMes."
        )
    )
    parser.add_argument("--ifdata", required=True, help="Caminho da base IFData wide.")
    parser.add_argument("--statements", required=True, help="Caminho da base statements.")
    parser.add_argument("--macro", required=True, help="Caminho da base macro mensal.")
    parser.add_argument(
        "-o", "--out-prefix",
        default="base_final_bancos",
        help="Prefixo dos arquivos de saída, sem extensão obrigatória.",
    )
    parser.add_argument(
        "--regime",
        choices=["prudencial", "conglomerado", "todos"],
        default="prudencial",
        help="Regime do IFData a utilizar. Recomendação: prudencial.",
    )
    parser.add_argument(
        "--incluir-ambiguos",
        action="store_true",
        help="Inclui entidades com cod_prudencial ambíguo. Não recomendado para modelagem.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    result = merge_all(
        ifdata_path=args.ifdata,
        statements_path=args.statements,
        macro_path=args.macro,
        out_prefix=args.out_prefix,
        regime=args.regime,
        excluir_ambiguos=not args.incluir_ambiguos,
    )

    stats = result["stats"]
    print("Consolidação concluída.")
    print(f"Base final: {result['merged_xlsx']}")
    print(f"Linhas na base final: {stats['linhas_base_final']}")
    print(f"Entidades na base final: {stats['entidades_base_final']}")
    print(f"Entidades com statements: {stats['entidades_com_statements']}")
    print(f"Linhas sem statements: {stats['linhas_sem_statements']}")
    print(f"Códigos IFData sem mapeamento: {stats['codigos_ifdata_sem_mapeamento']}")
    if stats["codigos_prudenciais_ambiguos_excluidos"]:
        print(f"Códigos prudenciais ambíguos excluídos: {stats['codigos_prudenciais_ambiguos_excluidos']}")


if __name__ == "__main__":
    main()
