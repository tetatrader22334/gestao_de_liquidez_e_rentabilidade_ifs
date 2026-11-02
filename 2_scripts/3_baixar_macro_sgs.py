# -*- coding: utf-8 -*-
"""
baixar_macro_sgs.py
Baixa séries macroeconômicas do Banco Central (SGS/BCData) e salva em CSV.

Exemplos:
  python baixar_macro_sgs.py --start 2010-01-01 --end 2025-12-31 --out macro.csv
  python baixar_macro_sgs.py --series ipca,igpm,igpdi,pib_trimestral_sa --out macro.csv
  python baixar_macro_sgs.py --add selic=11 --series ipca,selic --out macro.csv

Dependências:
  pip install pandas requests
"""

from __future__ import annotations

import argparse
import datetime as dt
from collections import OrderedDict
from typing import Dict, Iterable, Tuple

import pandas as pd
import requests


# Séries padrão (códigos SGS):
# - IPCA (variação mensal, %) -> 433
# - IGP-M (variação mensal, %) -> 189
# - IGP-DI (variação mensal, %) -> 190
# - PIB trimestral dessazonalizado (índice) -> 22109
DEFAULT_SERIES: "OrderedDict[str, int]" = OrderedDict(
    [
        ("selic", 4390),  # taxa Selic (mensal, %) - código 11
        ("pib_trimestral_sa", 22109),
        ("ipca", 433),
        ("igpm", 189),
        ("igpdi", 190),
        # Extras (desativados por padrão; inclua via --series)
        ("pib_trimestral_obs", 22099),
        ("pib_anual_nominal", 1207),
        ("pib_mensal_nominal", 4380),
    ]
)


def _to_ddmmyyyy(date_str: str) -> str:
    """
    Aceita 'YYYY-MM-DD' ou 'DD/MM/YYYY' e devolve 'DD/MM/YYYY' (formato da API SGS).
    """
    date_str = date_str.strip()
    if not date_str:
        raise ValueError("Data vazia.")

    # Já está em DD/MM/YYYY?
    if "/" in date_str:
        parts = date_str.split("/")
        if len(parts) == 3 and len(parts[2]) == 4:
            # valida minimamente
            day, month, year = map(int, parts)
            _ = dt.date(year, month, day)
            return f"{day:02d}/{month:02d}/{year:04d}"

    # Tenta ISO YYYY-MM-DD
    try:
        d = dt.date.fromisoformat(date_str)
        return d.strftime("%d/%m/%Y")
    except Exception as e:
        raise ValueError(
            f"Data inválida: '{date_str}'. Use 'YYYY-MM-DD' ou 'DD/MM/YYYY'."
        ) from e


def fetch_sgs_series(code: int, start: str, end: str, timeout: int = 30) -> pd.Series:
    """
    Baixa uma série do SGS (BCData) e retorna pd.Series (index=datetime, values=float).
    Endpoint:
      https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados?formato=json&dataInicial=DD/MM/AAAA&dataFinal=DD/MM/AAAA
    """
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
    params = {"formato": "json", "dataInicial": start, "dataFinal": end}

    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    data = r.json()

    if not isinstance(data, list) or len(data) == 0:
        # Pode acontecer para janelas de datas sem observações
        return pd.Series(dtype="float64", name=str(code))

    df = pd.DataFrame(data)
    # Campos típicos: 'data' (DD/MM/YYYY) e 'valor' (string com vírgula decimal)
    if "data" not in df.columns or "valor" not in df.columns:
        raise ValueError(f"Formato inesperado para a série {code}: chaves={list(df.columns)}")

    df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
    df["valor"] = (
        df["valor"]
        .astype(str)
        .str.replace(".", "", regex=False)   # remove separador de milhar (se houver)
        .str.replace(",", ".", regex=False)  # vírgula -> ponto
    )
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")

    s = df.set_index("data")["valor"].sort_index()
    s.name = str(code)
    return s


def build_series_map(series_keys_csv: str, add_items: Iterable[str]) -> Dict[str, int]:
    """
    Define quais séries baixar:
      - --series: lista de chaves separadas por vírgula (ex.: "ipca,igpm,pib_trimestral_sa")
      - --add: itens "nome=codigo" para incluir/override
    """
    series_map: Dict[str, int] = dict(DEFAULT_SERIES)

    # aplica --add (override / new)
    for item in add_items:
        if "=" not in item:
            raise ValueError(f"--add inválido: '{item}'. Use nome=codigo (ex.: selic=11)")
        name, code_str = item.split("=", 1)
        name = name.strip()
        code_str = code_str.strip()
        if not name:
            raise ValueError(f"--add inválido (nome vazio): '{item}'")
        try:
            code = int(code_str)
        except ValueError as e:
            raise ValueError(f"--add inválido (código não-inteiro): '{item}'") from e
        series_map[name] = code

    # se --series vier vazio, usa o conjunto padrão "mínimo"
    if not series_keys_csv.strip():
        # “mínimo”: só as 4 primeiras
        return {k: series_map[k] for k in ["ipca", "igpm", "igpdi", "pib_trimestral_sa"]}

    keys = [k.strip() for k in series_keys_csv.split(",") if k.strip()]
    unknown = [k for k in keys if k not in series_map]
    if unknown:
        known = ", ".join(sorted(series_map.keys()))
        raise ValueError(f"Séries desconhecidas: {unknown}. Disponíveis: {known}")
    return {k: series_map[k] for k in keys}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2010-01-01", help="Data inicial (YYYY-MM-DD ou DD/MM/YYYY).")
    ap.add_argument(
        "--end",
        default=dt.date.today().isoformat(),
        help="Data final (YYYY-MM-DD ou DD/MM/YYYY). Default: hoje.",
    )
    ap.add_argument(
        "--series",
        default="",
        help="Chaves separadas por vírgula. Ex.: ipca,igpm,igpdi,pib_trimestral_sa. "
             "Se vazio, baixa o conjunto padrão mínimo.",
    )
    ap.add_argument(
        "--add",
        action="append",
        default=[],
        help="Adicionar/override série no formato nome=codigo. Pode repetir. Ex.: --add selic=11",
    )
    ap.add_argument("--out", default="macro_sgs.csv", help="Arquivo de saída CSV.")
    ap.add_argument("--timeout", type=int, default=30, help="Timeout (s) para requisições HTTP.")
    args = ap.parse_args()

    start = _to_ddmmyyyy(args.start)
    end = _to_ddmmyyyy(args.end)

    series_map = build_series_map(args.series, args.add)

    frames = []
    for name, code in series_map.items():
        s = fetch_sgs_series(code, start=start, end=end, timeout=args.timeout)
        frames.append(s.rename(name))

    df = pd.concat(frames, axis=1).sort_index()

    # Salva em CSV
    df.to_csv(args.out, index_label="date", encoding="utf-8")
    print(f"[OK] Salvo: {args.out}")
    print(f"[INFO] Linhas: {len(df):,} | Colunas: {df.shape[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
