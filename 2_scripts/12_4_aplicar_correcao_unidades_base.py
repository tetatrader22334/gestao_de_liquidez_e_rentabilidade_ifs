#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aplica correções de unidade e consistência à base da dissertação.

Uso básico:
    python 12_4_aplicar_correcao_unidades_base.py --input bases/base.xlsx --output bases/base_un_ajustada.xlsx

O script preserva as colunas originais e cria colunas corrigidas/padronizadas.
Por padrão, também remove bs_totalLiab quando ela for duplicata de bs_totalAssets.

Principais correções:
1. Converte LCR e NSFR de percentual cheio para decimal.
2. Padroniza índices regulatórios já em decimal com sufixo _dec.
3. Converte IPCA e Selic de centésimos de ponto percentual para decimal e percentual.
4. Converte PIB trimestral dessazonalizado de índice x100 para índice.
5. Calcula crescimento trimestral do PIB por AnoMes.
6. Recalcula total de ativos da amostra, market share e HHI por período.
7. Marca exposicao_total = 0 como missing quando razao_de_alavancagem está ausente.
8. Gera relatório de validação em JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import numpy as np
import pandas as pd


# -----------------------------------------------------------------------------
# Configurações centrais
# -----------------------------------------------------------------------------

LCR_NSFR_PERCENT_COLS = [
    "lcr",
    "nsfr",
]

CAPITAL_RATIO_DECIMAL_COLS = [
    "razao_de_alavancagem",
    "indice_de_basileia",
    "indice_de_capital_nivel_i",
    "indice_de_capital_principal",
    "indice_de_imobilizacao",
]

MACRO_BPS_COLS = [
    "ipca_media_trimestre",
    "ipca_soma_trimestre",
    "ipca_fim_trimestre",
    "selic_media_trimestre",
    "selic_fim_trimestre",
]

MONETARY_LOG_CANDIDATES = [
    "bs_totalAssets",
    "ativos_totais_banco_brl",
    "cap_depositos",
    "cap_depositos_prazo",
    "cap_depositos_vista",
    "cap_recursos_mercado_aberto",
    "cap_recursos_aceites_emissao_titulos",
    "cap_obrigacoes_por_emprestimos_repasses",
    "credito_total",
    "operacoes_de_credito",
]


# -----------------------------------------------------------------------------
# Funções auxiliares
# -----------------------------------------------------------------------------

def existing(columns: Iterable[str], df: pd.DataFrame) -> list[str]:
    """Retorna apenas as colunas existentes no DataFrame."""
    return [col for col in columns if col in df.columns]


def read_table(path: Path, sheet_name: Optional[str] = None) -> pd.DataFrame:
    """Lê arquivo xlsx, xls, csv, parquet ou feather."""
    suffix = path.suffix.lower()

    if suffix in {".xlsx", ".xls", ".xlsm"}:
        return pd.read_excel(path, sheet_name=sheet_name or 0)
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".feather":
        return pd.read_feather(path)

    raise ValueError(
        f"Formato não suportado: {suffix}. Use .xlsx, .xls, .xlsm, .csv, .parquet ou .feather."
    )


def write_table(df: pd.DataFrame, path: Path) -> None:
    """Grava arquivo xlsx, csv, parquet ou feather de acordo com a extensão."""
    suffix = path.suffix.lower()
    path.parent.mkdir(parents=True, exist_ok=True)

    if suffix in {".xlsx", ".xls", ".xlsm"}:
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="base_corrigida")
        return
    if suffix == ".csv":
        df.to_csv(path, index=False, encoding="utf-8-sig")
        return
    if suffix == ".parquet":
        df.to_parquet(path, index=False)
        return
    if suffix == ".feather":
        df.to_feather(path)
        return

    raise ValueError(
        f"Formato de saída não suportado: {suffix}. Use .xlsx, .csv, .parquet ou .feather."
    )


def to_numeric_safe(series: pd.Series) -> pd.Series:
    """Converte uma Series para numérica preservando NaN quando houver falha."""
    if pd.api.types.is_numeric_dtype(series):
        return series

    # Trata números com vírgula decimal em bases eventualmente exportadas como texto.
    as_str = (
        series.astype(str)
        .str.strip()
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .replace({"": np.nan, "nan": np.nan, "None": np.nan})
    )
    return pd.to_numeric(as_str, errors="coerce")


def sort_key_anomes(series: pd.Series) -> pd.Series:
    """Cria chave ordenável para AnoMes, aceitando int, float ou string no formato AAAAMM."""
    # Extrai dígitos para lidar com 202403, 202403.0 ou strings.
    digits = series.astype(str).str.extract(r"(\d{6})", expand=False)
    return pd.to_numeric(digits, errors="coerce")


def add_log_column(df: pd.DataFrame, col: str, suffix: str = "_log") -> None:
    """Cria log natural para valores positivos; valores <= 0 viram NaN."""
    new_col = f"{col}{suffix}"
    values = to_numeric_safe(df[col])
    df[new_col] = np.where(values > 0, np.log(values), np.nan)


# -----------------------------------------------------------------------------
# Correções principais
# -----------------------------------------------------------------------------

def apply_unit_corrections(
    df: pd.DataFrame,
    drop_duplicate_total_liab: bool = True,
    create_logs: bool = True,
) -> tuple[pd.DataFrame, Dict[str, Any]]:
    """Aplica correções e retorna DataFrame corrigido + relatório."""
    df = df.copy()
    report: Dict[str, Any] = {
        "n_linhas": int(len(df)),
        "n_colunas_original": int(df.shape[1]),
        "colunas_criadas": [],
        "avisos": [],
        "validacoes": {},
    }

    # -------------------------------------------------------------------------
    # Chave temporal auxiliar
    # -------------------------------------------------------------------------
    if "AnoMes" in df.columns:
        df["AnoMes_ord"] = sort_key_anomes(df["AnoMes"])
        report["colunas_criadas"].append("AnoMes_ord")
    else:
        report["avisos"].append("Coluna AnoMes não encontrada; cálculos por período foram limitados.")

    # -------------------------------------------------------------------------
    # 1. LCR e NSFR: percentual cheio -> decimal
    # -------------------------------------------------------------------------
    for col in existing(LCR_NSFR_PERCENT_COLS, df):
        df[col] = to_numeric_safe(df[col])
        new_col = f"{col}_dec"
        df[new_col] = df[col] / 100.0
        report["colunas_criadas"].append(new_col)

    # -------------------------------------------------------------------------
    # 2. Índices de capital já em decimal: criar cópias padronizadas _dec
    # -------------------------------------------------------------------------
    for col in existing(CAPITAL_RATIO_DECIMAL_COLS, df):
        df[col] = to_numeric_safe(df[col])
        new_col = f"{col}_dec"
        df[new_col] = df[col]
        report["colunas_criadas"].append(new_col)

        # Sinaliza magnitudes suspeitas acima de 1, que indicariam percentual cheio.
        max_val = df[col].max(skipna=True)
        if pd.notna(max_val) and max_val > 1:
            report["avisos"].append(
                f"{col} possui máximo maior que 1 ({max_val:.6g}); verifique se não está em percentual cheio."
            )

    # -------------------------------------------------------------------------
    # 3. IPCA e Selic: centésimos de ponto percentual -> decimal e percentual
    # -------------------------------------------------------------------------
    for col in existing(MACRO_BPS_COLS, df):
        df[col] = to_numeric_safe(df[col])
        col_dec = f"{col}_dec"
        col_pct = f"{col}_pct"
        df[col_dec] = df[col] / 10000.0
        df[col_pct] = df[col] / 100.0
        report["colunas_criadas"].extend([col_dec, col_pct])

    # -------------------------------------------------------------------------
    # 4. PIB: índice x100 -> índice; crescimento trimestral por AnoMes
    # -------------------------------------------------------------------------
    if "pib_trimestral_sa" in df.columns:
        df["pib_trimestral_sa"] = to_numeric_safe(df["pib_trimestral_sa"])
        df["pib_indice_sa"] = df["pib_trimestral_sa"] / 100.0
        report["colunas_criadas"].append("pib_indice_sa")

        if "AnoMes_ord" in df.columns:
            pib_series = (
                df[["AnoMes_ord", "pib_indice_sa"]]
                .dropna(subset=["AnoMes_ord"])
                .drop_duplicates(subset=["AnoMes_ord"])
                .sort_values("AnoMes_ord")
            )
            pib_series["pib_crescimento_tri"] = pib_series["pib_indice_sa"].pct_change()
            df = df.merge(
                pib_series[["AnoMes_ord", "pib_crescimento_tri"]],
                on="AnoMes_ord",
                how="left",
            )
            report["colunas_criadas"].append("pib_crescimento_tri")
    else:
        report["avisos"].append("Coluna pib_trimestral_sa não encontrada.")

    # -------------------------------------------------------------------------
    # 5. Ativos, market share e HHI corrigidos
    # -------------------------------------------------------------------------
    if "bs_totalAssets" in df.columns:
        df["bs_totalAssets"] = to_numeric_safe(df["bs_totalAssets"])
        df["ativos_totais_banco_brl"] = df["bs_totalAssets"]
        report["colunas_criadas"].append("ativos_totais_banco_brl")

        group_col = "AnoMes_ord" if "AnoMes_ord" in df.columns else None
        if group_col:
            df["ativos_totais_amostra_brl"] = df.groupby(group_col)["bs_totalAssets"].transform("sum")
            df["market_share_corrigido_dec"] = df["bs_totalAssets"] / df["ativos_totais_amostra_brl"]
            df["hhi_contribuicao_corrigido_dec"] = df["market_share_corrigido_dec"] ** 2
            df["hhi_periodo_corrigido_dec"] = df.groupby(group_col)["hhi_contribuicao_corrigido_dec"].transform("sum")
            df["hhi_periodo_corrigido_10000"] = df["hhi_periodo_corrigido_dec"] * 10000.0
            report["colunas_criadas"].extend([
                "ativos_totais_amostra_brl",
                "market_share_corrigido_dec",
                "hhi_contribuicao_corrigido_dec",
                "hhi_periodo_corrigido_dec",
                "hhi_periodo_corrigido_10000",
            ])

            # Validação: soma do market share por período deve ser próxima de 1.
            ms_sum = df.groupby(group_col)["market_share_corrigido_dec"].sum(min_count=1)
            report["validacoes"]["market_share_corrigido_soma_min"] = float(ms_sum.min(skipna=True))
            report["validacoes"]["market_share_corrigido_soma_max"] = float(ms_sum.max(skipna=True))
        else:
            report["avisos"].append("Não foi possível recalcular market share e HHI sem AnoMes.")
    else:
        report["avisos"].append("Coluna bs_totalAssets não encontrada; market share e HHI não foram recalculados.")

    # Mantém rastreabilidade do HHI original.
    if "hhi" in df.columns:
        df["hhi_original"] = to_numeric_safe(df["hhi"])
        report["colunas_criadas"].append("hhi_original")
        if "market_share" in df.columns:
            df["market_share"] = to_numeric_safe(df["market_share"])
            diff = (df["hhi_original"] - df["market_share"] ** 2).abs()
            report["validacoes"]["hhi_original_igual_market_share_ao_quadrado_diff_max"] = (
                None if diff.dropna().empty else float(diff.max(skipna=True))
            )

    # -------------------------------------------------------------------------
    # 6. bs_totalLiab duplicada de bs_totalAssets
    # -------------------------------------------------------------------------
    if "bs_totalLiab" in df.columns and "bs_totalAssets" in df.columns:
        df["bs_totalLiab"] = to_numeric_safe(df["bs_totalLiab"])
        diff_liab_assets = (df["bs_totalLiab"] - df["bs_totalAssets"]).abs()
        max_diff = None if diff_liab_assets.dropna().empty else float(diff_liab_assets.max(skipna=True))
        report["validacoes"]["bs_totalLiab_vs_bs_totalAssets_diff_max"] = max_diff

        if max_diff == 0.0:
            df["bs_totalLiab_original_duplicado_de_assets"] = df["bs_totalLiab"]
            report["colunas_criadas"].append("bs_totalLiab_original_duplicado_de_assets")
            if drop_duplicate_total_liab:
                df = df.drop(columns=["bs_totalLiab"])
                report["avisos"].append(
                    "bs_totalLiab removida porque é idêntica a bs_totalAssets em todos os registros válidos. "
                    "A cópia foi preservada em bs_totalLiab_original_duplicado_de_assets."
                )
        else:
            report["avisos"].append(
                "bs_totalLiab não é perfeitamente idêntica a bs_totalAssets; coluna foi mantida."
            )

    # -------------------------------------------------------------------------
    # 7. exposicao_total = 0 e razao_de_alavancagem ausente -> NaN
    # -------------------------------------------------------------------------
    if "exposicao_total" in df.columns:
        df["exposicao_total"] = to_numeric_safe(df["exposicao_total"])
        if "razao_de_alavancagem" in df.columns:
            mask_exposicao_missing = (df["exposicao_total"] == 0) & (df["razao_de_alavancagem"].isna())
            n_corrigidos = int(mask_exposicao_missing.sum())
            df.loc[mask_exposicao_missing, "exposicao_total"] = np.nan
            report["validacoes"]["exposicao_total_zeros_convertidos_para_nan"] = n_corrigidos
            if n_corrigidos > 0:
                report["avisos"].append(
                    f"{n_corrigidos} valores de exposicao_total iguais a zero foram convertidos para NaN "
                    "porque razao_de_alavancagem estava ausente."
                )
        else:
            report["avisos"].append(
                "Coluna razao_de_alavancagem não encontrada; zeros em exposicao_total não foram tratados."
            )

    # -------------------------------------------------------------------------
    # 8. Logs de variáveis monetárias positivas
    # -------------------------------------------------------------------------
    if create_logs:
        for col in existing(MONETARY_LOG_CANDIDATES, df):
            log_col = f"{col}_log"
            if log_col not in df.columns:
                add_log_column(df, col)
                report["colunas_criadas"].append(log_col)

    # -------------------------------------------------------------------------
    # 9. Ordenação final
    # -------------------------------------------------------------------------
    sort_cols = []
    if "AnoMes_ord" in df.columns:
        sort_cols.append("AnoMes_ord")
    if "id_entidade" in df.columns:
        sort_cols.append("id_entidade")
    elif "Ticker" in df.columns:
        sort_cols.append("Ticker")

    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)

    report["n_colunas_final"] = int(df.shape[1])
    report["n_colunas_criadas"] = int(len(report["colunas_criadas"]))

    return df, report


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Corrige unidades e consistência da base de bancos da dissertação."
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Caminho da base de entrada. Ex.: base.xlsx",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="base_corrigida.xlsx",
        help="Caminho da base corrigida. Ex.: base_corrigida.xlsx",
    )
    parser.add_argument(
        "--sheet-name",
        default=None,
        help="Nome da aba do Excel. Se omitido, lê a primeira aba.",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Caminho do relatório JSON. Se omitido, usa o nome da saída com sufixo _relatorio.json.",
    )
    parser.add_argument(
        "--keep-bs-total-liab",
        action="store_true",
        help="Mantém bs_totalLiab mesmo se for duplicata perfeita de bs_totalAssets.",
    )
    parser.add_argument(
        "--no-logs",
        action="store_true",
        help="Não cria colunas logarítmicas para variáveis monetárias."
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    input_path = Path(args.input)
    output_path = Path(args.output)
    report_path = Path(args.report) if args.report else output_path.with_name(
        f"{output_path.stem}_relatorio.json"
    )

    if not input_path.exists():
        print(f"[ERRO] Arquivo de entrada não encontrado: {input_path}", file=sys.stderr)
        return 1

    try:
        df = read_table(input_path, sheet_name=args.sheet_name)
        corrected, report = apply_unit_corrections(
            df,
            drop_duplicate_total_liab=not args.keep_bs_total_liab,
            create_logs=not args.no_logs,
        )
        write_table(corrected, output_path)

        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"[OK] Base corrigida gravada em: {output_path}")
        print(f"[OK] Relatório de validação gravado em: {report_path}")
        print(f"[INFO] Linhas: {report['n_linhas']}")
        print(f"[INFO] Colunas originais: {report['n_colunas_original']}")
        print(f"[INFO] Colunas finais: {report['n_colunas_final']}")
        print(f"[INFO] Colunas criadas: {report['n_colunas_criadas']}")

        if report["avisos"]:
            print("\n[AVISOS]")
            for aviso in report["avisos"]:
                print(f"- {aviso}")

        return 0

    except Exception as exc:
        print(f"[ERRO] Falha ao processar a base: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
