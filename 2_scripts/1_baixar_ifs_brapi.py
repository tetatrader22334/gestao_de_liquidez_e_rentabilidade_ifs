# -*- coding: utf-8 -*-
"""
baixar_ifs_brapi.py
Baixa (1) cotações + histórico (OHLCV) e (2) demonstrações/módulos financeiros via BRAPI.

Docs (endpoint único):
  GET https://brapi.dev/api/quote/{tickers}
  - range: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
  - interval: 1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo
  - modules: summaryProfile, balanceSheetHistory(Quarterly), incomeStatementHistory(Quarterly),
             cashflowHistory(Quarterly), valueAddedHistory(Quarterly), defaultKeyStatistics, financialData, etc.

Uso:
  pip install requests pandas
  python baixar_ifs_brapi.py --outdir data_brapi --range max --interval 1d --token vUiHbLoqN8guLXMxq3NFKa
  python baixar_ifs_brapi.py --tickers BBAS3,BBDC4 --modules balanceSheetHistoryQuarterly,incomeStatementHistoryQuarterly

Observação IMPORTANTÍSSIMA:
- As IFs abaixo foram mapeadas para tickers "padrão" (ex.: PN/UNIT). Se você preferir outro papel,
  ajuste no dicionário NAME_TO_TICKER ou passe --tickers / --mapping-csv.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests


API_BASE = "https://brapi.dev/api"

# Token padrão (você pode sobrescrever via --token ou variável de ambiente BRAPI_TOKEN)
DEFAULT_TOKEN = "vUiHbLoqN8guLXMxq3NFKa"

# Mapeamento "best effort" (ajuste se desejar outro papel/classe)
NAME_TO_TICKER: Dict[str, str] = {
    "Alfa Holding": "RPAD6",
    "Banestes": "BEES4",
    "ABC Brasil": "ABCB4",
    "Banco Amazônia": "BAZA3",
    "Bradesco": "BBDC4",
    "Banco do Brasil": "BBAS3",
    "BTG Pactual": "BPAC11",
    "Banco do estado de Sergipe": "BGIP4",
    "Banrisul": "BRSR6",
    "Banco mercantil de investimentos": "BMIN4",
    "Banco mercantil do Brasil": "BMEB4",
    "Banco do Nordeste": "BNBR3",
    "Banco Pan": "BPAN4",
    "Banco Pine": "PINE4",
    "Santander Brasil": "SANB11",
    "BRB Banco de Brasília": "BSLI4",
}

# Módulos (demonstrações)
DEFAULT_MODULES = ",".join(
    [
        "summaryProfile",
        "balanceSheetHistoryQuarterly",
        "incomeStatementHistoryQuarterly",
        "cashflowHistoryQuarterly",
        "valueAddedHistoryQuarterly",
        "defaultKeyStatistics",
        "financialData",
    ]
)


@dataclass
class BrapiClient:
    token: str
    timeout: int = 30
    max_retries: int = 5
    sleep_base: float = 1.0  # segundos (backoff simples)
    session: Optional[requests.Session] = None

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = requests.Session()

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{API_BASE}{path}"
        params = dict(params or {})
        if self.token:
            params.setdefault("token", self.token)

        last_err: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                r = self.session.get(url, params=params, timeout=self.timeout)
                # 402 = Payment Required (limite do plano) / 401/404 etc.
                if r.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"HTTP {r.status_code}: {r.text[:200]}", response=r)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                last_err = e
                # Se for 402/401/404, não faz sentido ficar tentando
                if isinstance(e, requests.HTTPError) and getattr(e, "response", None) is not None:
                    code = e.response.status_code
                    if code in (401, 402, 404, 400):
                        raise
                time.sleep(self.sleep_base * attempt)

        raise RuntimeError(f"Falha após {self.max_retries} tentativas em {url}") from last_err


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def chunked(items: List[str], n: int) -> Iterable[List[str]]:
    for i in range(0, len(items), n):
        yield items[i : i + n]


def extract_historical_prices(result_obj: Dict[str, Any]) -> pd.DataFrame:
    """
    Extrai histórico OHLCV do objeto de 1 ticker vindo em results[i].
    BRAPI costuma retornar em 'historicalDataPrice' (ou às vezes 'historicalData').
    """
    symbol = result_obj.get("symbol") or result_obj.get("stock") or result_obj.get("ticker") or None
    hist = (
        result_obj.get("historicalDataPrice")
        or result_obj.get("historicalData")
        or result_obj.get("historicalDataPriceList")
        or []
    )
    if not isinstance(hist, list) or not hist:
        return pd.DataFrame()

    df = pd.DataFrame(hist).copy()
    # Campo 'date' pode vir em epoch (segundos) ou string
    if "date" in df.columns:
        if pd.api.types.is_numeric_dtype(df["date"]):
            df["date"] = pd.to_datetime(df["date"], unit="s", errors="coerce")
        else:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")

    df.insert(0, "ticker", symbol)
    # Normaliza nomes comuns
    rename_map = {
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
        "adjclose": "adj_close",
        "adjustedClose": "adj_close",
    }
    for k, v in rename_map.items():
        if k in df.columns and v not in df.columns:
            df = df.rename(columns={k: v})

    cols_prefer = ["ticker", "date", "open", "high", "low", "close", "adj_close", "volume"]
    cols = [c for c in cols_prefer if c in df.columns] + [c for c in df.columns if c not in cols_prefer]
    return df[cols].sort_values(["ticker", "date"]).reset_index(drop=True)


def _find_first_list_in_obj(obj: Any, depth: int = 0, max_depth: int = 5) -> Optional[List[Dict[str, Any]]]:
    """
    Heurística: em módulos de demonstrações, geralmente existe uma lista de "statements" em algum nível.
    """
    if depth > max_depth:
        return None
    if isinstance(obj, list):
        if obj and all(isinstance(x, dict) for x in obj):
            return obj  # tipo lista de dicts
        return None
    if isinstance(obj, dict):
        for _, v in obj.items():
            found = _find_first_list_in_obj(v, depth + 1, max_depth)
            if found is not None:
                return found
    return None


def extract_module_table(result_obj: Dict[str, Any], module_key: str) -> pd.DataFrame:
    """
    Tenta extrair uma tabela (lista de dicts) do módulo (ex.: balanceSheetHistoryQuarterly).
    """
    symbol = result_obj.get("symbol") or result_obj.get("stock") or result_obj.get("ticker") or None
    mod = result_obj.get(module_key)
    if not isinstance(mod, dict):
        return pd.DataFrame()

    rows = _find_first_list_in_obj(mod)
    if not rows:
        return pd.DataFrame()

    df = pd.json_normalize(rows)
    df.insert(0, "ticker", symbol)
    df.insert(1, "module", module_key)
    return df


def load_mapping_csv(path: Path) -> Dict[str, str]:
    """
    CSV com colunas: institution,ticker
    """
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    if "institution" not in cols or "ticker" not in cols:
        raise ValueError("CSV de mapeamento deve ter colunas: institution,ticker")
    mapping = dict(zip(df[cols["institution"]].astype(str), df[cols["ticker"]].astype(str)))
    return mapping


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", default=os.getenv("BRAPI_TOKEN", DEFAULT_TOKEN), help="Token BRAPI (ou BRAPI_TOKEN).")
    ap.add_argument("--outdir", default="data_brapi", help="Pasta de saída.")
    ap.add_argument("--range", dest="range_", default="max", help="Período do histórico (ex.: max, 10y, 5y...).")
    ap.add_argument("--interval", default="1d", help="Granularidade do histórico (ex.: 1d, 1wk, 1mo...).")
    ap.add_argument(
        "--modules",
        default=DEFAULT_MODULES,
        help="Módulos (demonstrações) separados por vírgula.",
    )
    ap.add_argument(
        "--tickers",
        default="",
        help="Lista de tickers separada por vírgula. Se vazio, usa o mapeamento das IFs.",
    )
    ap.add_argument(
        "--mapping-csv",
        default="",
        help="CSV opcional para sobrescrever mapeamento (colunas: institution,ticker).",
    )
    ap.add_argument("--sleep", type=float, default=0.2, help="Pausa (s) entre requisições.")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--max-retries", type=int, default=5)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    ensure_dir(outdir)
    raw_dir = outdir / "raw_json"
    ensure_dir(raw_dir)
    quotes_dir = raw_dir / "quotes"
    stmts_dir = raw_dir / "statements"
    ensure_dir(quotes_dir)
    ensure_dir(stmts_dir)

    # Resolve tickers
    mapping = dict(NAME_TO_TICKER)
    if args.mapping_csv:
        mapping.update(load_mapping_csv(Path(args.mapping_csv)))

    if args.tickers.strip():
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        tickers = [t.upper() for t in mapping.values()]

    # Remove duplicados mantendo ordem
    seen = set()
    tickers = [t for t in tickers if not (t in seen or seen.add(t))]

    client = BrapiClient(
        token=args.token,
        timeout=args.timeout,
        max_retries=args.max_retries,
        sleep_base=max(0.5, float(args.sleep)),
    )

    # 1) Cotações + histórico
    all_prices: List[pd.DataFrame] = []
    quotes_summary_rows: List[Dict[str, Any]] = []

    # BRAPI permite múltiplos tickers por requisição (geralmente até 10 por chamada, depende do plano).
    for chunk in chunked(tickers, 10):
        tickers_str = ",".join(chunk)
        params = {
            "range": args.range_,
            "interval": args.interval,
            # pode incluir também:
            # "fundamental": "true",
            # "dividends": "true",
        }
        data = client.get(f"/quote/{tickers_str}", params=params)
        write_json(quotes_dir / f"quote_{tickers_str.replace(',','_')}.json", data)

        results = data.get("results") or []
        for obj in results:
            # histórico
            dfp = extract_historical_prices(obj)
            if not dfp.empty:
                all_prices.append(dfp)

            # resumo (cotação atual)
            quotes_summary_rows.append(
                {
                    "ticker": obj.get("symbol"),
                    "shortName": obj.get("shortName"),
                    "longName": obj.get("longName"),
                    "currency": obj.get("currency"),
                    "regularMarketPrice": obj.get("regularMarketPrice"),
                    "regularMarketChangePercent": obj.get("regularMarketChangePercent"),
                    "regularMarketTime": obj.get("regularMarketTime"),
                    "marketCap": obj.get("marketCap"),
                    "volume": obj.get("regularMarketVolume") or obj.get("volume"),
                }
            )

        time.sleep(float(args.sleep))

    df_quotes_summary = pd.DataFrame(quotes_summary_rows).dropna(subset=["ticker"]).drop_duplicates("ticker")
    df_quotes_summary.to_csv(outdir / "quotes_summary.csv", index=False, encoding="utf-8")

    if all_prices:
        df_prices = pd.concat(all_prices, ignore_index=True)
        df_prices.to_csv(outdir / "prices_ohlcv.csv", index=False, encoding="utf-8")
    else:
        print("[WARN] Nenhum histórico retornado. Verifique range/interval e os tickers.")
        df_prices = pd.DataFrame()

    # 2) Demonstrações via modules (1 ticker por requisição, para facilitar o raw e o parsing)
    modules = [m.strip() for m in (args.modules or "").split(",") if m.strip()]
    module_tables: Dict[str, List[pd.DataFrame]] = {m: [] for m in modules}

    for t in tickers:
        params = {"modules": ",".join(modules)}
        data = client.get(f"/quote/{t}", params=params)
        write_json(stmts_dir / f"statements_{t}.json", data)

        results = data.get("results") or []
        if not results:
            print(f"[WARN] Sem results para {t}")
            time.sleep(float(args.sleep))
            continue

        obj = results[0]
        for m in modules:
            dft = extract_module_table(obj, m)
            if not dft.empty:
                module_tables[m].append(dft)

        time.sleep(float(args.sleep))

    # Exporta tabelas normalizadas (uma por módulo) — além do raw JSON
    for m, dfs in module_tables.items():
        if not dfs:
            continue
        dfm = pd.concat(dfs, ignore_index=True)
        # tenta padronizar coluna de data/fim de período se existir
        for cand in ["endDate.fmt", "endDate", "asOfDate", "periodEndDate", "date", "endDate.raw"]:
            if cand in dfm.columns:
                dfm = dfm.rename(columns={cand: "period_end"})
                break
        dfm.to_csv(outdir / f"{m}.csv", index=False, encoding="utf-8")

    # Salva também o mapeamento usado
    pd.DataFrame(
        [{"institution": k, "ticker": v} for k, v in mapping.items()]
    ).to_csv(outdir / "mapping_institution_ticker.csv", index=False, encoding="utf-8")

    print(f"[OK] Saída em: {outdir.resolve()}")
    print(f"[OK] tickers: {len(tickers)} | módulos: {len(modules)}")
    print(f"[OK] arquivos: prices_ohlcv.csv, quotes_summary.csv, *.json (raw), e módulos *.csv (quando disponíveis)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
