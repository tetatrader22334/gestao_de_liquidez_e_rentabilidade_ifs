#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Obtém LCR e NSFR de instituições financeiras brasileiras, priorizando fontes regulatórias
oficiais do Banco Central (Pilar 3 / DASFN). Quando o indicador regulatório não estiver
publicado para a instituição/período, gera proxies contábeis a partir dos Balancetes/COSIF.

Fluxo do script
---------------
1) Resolve a instituição (CNPJ/CNPJ8/nome/ticker).
2) Tenta obter valores oficiais em ordem:
   a) LIQ1 / LIQ2 (Pilar 3) -> LCR, HQLA, saídas líquidas, ASF, RSF, NSFR
   b) KM1 (Pilar 3)         -> LCR, HQLA, saídas líquidas, ASF, RSF, NSFR
3) Se algum indicador continuar indisponível, baixa o Balancete 4010 e monta proxies:
   - proxy_lcr_bs  = (Disponibilidades + Aplic. interfinanceiras de liquidez + 50% TVM)
                     / (Depósitos + captações de mercado + funding de atacado)
   - proxy_nsfr_bs = (PL + 90% depósitos + 50% funding de atacado)
                     / (0% caixa + 15% TVM + 50% interfinanceiro +
                        85% crédito + 100% ativo permanente)

IMPORTANTE
----------
- Os proxies NÃO substituem o LCR/NSFR regulatórios; são aproximações contábeis.
- A heurística de proxy usa nomes de contas COSIF e pode exigir pequenos ajustes caso o
  layout ou a nomenclatura pública do BCB mude.
- O script não grava seu token da BRAPI em arquivo. Passe por --brapi-token ou BRAPI_TOKEN.

Exemplos
--------
1) Por nomes, trimestre único:
   python 4_lcr_nsfr_bcb_v7.py --institutions "Alfa holding" --quarter "2014Q1:2024Q4"

2) Por nomes, múltiplos trimestres em lista:
   python 4_lcr_nsfr_bcb_v7.py --institutions "Bradesco;Banco do Brasil" --quarter "202403,202406,202409,202412"

3) Por faixa de trimestres:
   python 4_lcr_nsfr_bcb_v7.py --institutions "Bradesco" --quarter "2023Q1:2024Q4"

4) Por arquivo CSV (colunas aceitas: institution, nome, cnpj, cnpj8, ticker):
   python 4_lcr_nsfr_bcb_v7.py --input instituicoes.csv --quarter "202412;202503" --out saida.csv

5) Com tickers e apoio opcional da BRAPI:
   python 4_lcr_nsfr_bcb_v7.py --tickers "BBDC4,BBAS3,SANB11" --quarters "2024Q1:2024Q4" --brapi-token SEU_TOKEN
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import difflib
import io
import json
import math
import os
import re
import sys
import time
import zipfile
from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import quote

import requests


# =========================
# Configuração e constantes
# =========================

DASFN_BASE = "https://olinda.bcb.gov.br/olinda/servico/DASFN/versao/v1/odata/Recursos"
IFDATA_CADASTRO = "https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata/IfDataCadastro"
INSTITUICOES_FUNCIONAMENTO_RESOURCES = [
    "https://olinda.bcb.gov.br/olinda/servico/Instituicoes_em_funcionamento/versao/v1/odata/SedesBancoComMultCE?$format=json",
    "https://olinda.bcb.gov.br/olinda/servico/Instituicoes_em_funcionamento/versao/v1/odata/SedesSociedades?$format=json",
    "https://olinda.bcb.gov.br/olinda/servico/Instituicoes_em_funcionamento/versao/v1/odata/SedesCooperativas?$format=json",
]
BALANCETE_URL_TEMPLATE = (
    "https://www4.bcb.gov.br/fis/cosif/cont/balan/individualizados/{yyyymm}/4010/{yyyymm}-4010-{cnpj8}.ZIP"
)
BRAPI_QUOTE_URL = "https://brapi.dev/api/quote/{ticker}"

TIMEOUT = 40
RETRIES = 3
SLEEP_RETRY = 1.5
USER_AGENT = "Mateus-LCR-NSFR-Script/1.0"
EPS = 1e-9


# =========================
# Utilidades gerais
# =========================

def eprint(*args: Any) -> None:
    print(*args, file=sys.stderr)


def digits_only(value: Any) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def norm_text(value: Any) -> str:
    s = str(value or "").strip().lower()
    translit = str.maketrans(
        {
            "á": "a", "à": "a", "â": "a", "ã": "a", "ä": "a",
            "é": "e", "è": "e", "ê": "e", "ë": "e",
            "í": "i", "ì": "i", "î": "i", "ï": "i",
            "ó": "o", "ò": "o", "ô": "o", "õ": "o", "ö": "o",
            "ú": "u", "ù": "u", "û": "u", "ü": "u",
            "ç": "c",
        }
    )
    s = s.translate(translit)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def semver_key(value: str) -> Tuple[int, ...]:
    nums = re.findall(r"\d+", str(value or ""))
    return tuple(int(x) for x in nums) if nums else (0,)



def is_plausible_cnpj(value: Any, min_len: int = 8) -> bool:
    d = digits_only(value)
    if len(d) < min_len:
        return False
    # CNPJ completo pode começar com raiz 00000000 (ex.: Banco do Brasil),
    # então rejeitamos apenas se TODOS os dígitos disponíveis forem zero.
    return any(ch != "0" for ch in d)


def is_acceptable_cnpj8(value: Any) -> bool:
    d = digits_only(value)
    return len(d) >= 8


def source_priority(source: str) -> float:
    s = norm_text(source)
    if "sedesbancocommultce" in s:
        return 0.10
    if "ifdatacadastro" in s:
        return 0.06
    if "sedessociedades" in s:
        return 0.02
    if "sedescooperativas" in s:
        return 0.02
    return 0.0


def normalize_alias_name(value: str) -> str:
    raw = norm_text(value)
    aliases = {
        "abcb4": "banco abc brasil",
        "bbas3": "banco do brasil",
        "bbdc3": "banco bradesco",
        "bbdc4": "banco bradesco",
        "bpac11": "banco btg pactual",
        "itub3": "itau unibanco",
        "itub4": "itau unibanco",
        "sanb3": "banco santander brasil",
        "sanb4": "banco santander brasil",
        "sanb11": "banco santander brasil",
        "abc brasil": "banco abc brasil",
        "bradesco": "banco bradesco",
        "banco do brasil": "banco do brasil",
        "santander": "banco santander brasil",
        "itau": "itau unibanco",
        "itau unibanco": "itau unibanco",
        "btg pactual": "banco btg pactual",
    }
    return aliases.get(raw, raw)

def canonical_name_core(value: str) -> str:
    s = norm_text(value)
    if not s:
        return s
    tokens = [t for t in s.split() if t not in {"s", "a", "sa", "s a", "ltda", "me", "epp", "sc", "scp"}]
    return " ".join(tokens).strip()


def parse_decimal(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if math.isfinite(float(value)):
            return float(value)
        return None
    s = str(value).strip()
    if not s:
        return None
    s_norm = norm_text(s)
    if s_norm in {"na", "n a", "nan", "none", "null", "indisponivel", "sem informacao"}:
        return None

    # Trata formatos tipo 1.234.567,89 e 1,234,567.89
    s = s.replace("R$", "").replace("%", "").replace("\xa0", " ").strip()
    s = re.sub(r"\s+", "", s)
    if s.count(",") > 0 and s.count(".") > 0:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif s.count(",") > 0:
        s = s.replace(".", "").replace(",", ".")
    try:
        out = float(s)
        if math.isfinite(out):
            return out
    except Exception:
        return None
    return None


def default_quarter(today: Optional[dt.date] = None) -> str:
    today = today or dt.date.today()
    month = today.month
    year = today.year
    q_end = ((month - 1) // 3 + 1) * 3
    # usa o trimestre encerrado mais recente
    return f"{year}{q_end:02d}"


def normalize_quarter(raw: Optional[str]) -> str:
    if not raw:
        return default_quarter()
    s = digits_only(raw)
    if len(s) == 6 and s[-2:] in {"03", "06", "09", "12"}:
        return s
    m = re.fullmatch(r"(\d{4})Q([1-4])", str(raw).strip(), flags=re.I)
    if m:
        year = int(m.group(1))
        q = int(m.group(2))
        return f"{year}{q*3:02d}"
    raise ValueError(f"Trimestre inválido: {raw}. Use AAAAMM (ex.: 202412) ou AAAAQn (ex.: 2024Q4).")


def quarter_to_index(quarter: str) -> int:
    q = normalize_quarter(quarter)
    year = int(q[:4])
    month = int(q[4:6])
    qnum = month // 3
    return year * 4 + (qnum - 1)


def index_to_quarter(index: int) -> str:
    year, qzero = divmod(index, 4)
    month = (qzero + 1) * 3
    return f"{year}{month:02d}"


def expand_quarter_range(start: str, end: str) -> List[str]:
    start_q = normalize_quarter(start)
    end_q = normalize_quarter(end)
    i0 = quarter_to_index(start_q)
    i1 = quarter_to_index(end_q)
    if i0 > i1:
        raise ValueError(f"Faixa de trimestres inválida: {start} > {end}.")
    return [index_to_quarter(i) for i in range(i0, i1 + 1)]


def parse_quarters(raw_quarter: Optional[str] = None, raw_quarters: Optional[str] = None) -> List[str]:
    raw = raw_quarters if raw_quarters else raw_quarter
    if not raw:
        return [default_quarter()]

    tokens = [x.strip() for x in re.split(r"[;,\n]+", str(raw)) if x.strip()]
    out: List[str] = []
    seen: set[str] = set()

    for token in tokens:
        token = token.strip()
        m = re.fullmatch(r"(.+?)\s*(?::|\.\.|\s+-\s+)\s*(.+)", token, flags=re.I)
        if m:
            expanded = expand_quarter_range(m.group(1).strip(), m.group(2).strip())
        else:
            expanded = [normalize_quarter(token)]
        for q in expanded:
            if q not in seen:
                seen.add(q)
                out.append(q)
    return out


def choose_csv_dialect(sample: str) -> csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except Exception:
        class Simple(csv.Dialect):
            delimiter = ";"
            quotechar = '"'
            escapechar = None
            doublequote = True
            skipinitialspace = False
            lineterminator = "\n"
            quoting = csv.QUOTE_MINIMAL
        return Simple


def flatten(obj: Any, prefix: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                out.update(flatten(v, key))
            else:
                out[key] = v
    else:
        out[prefix or "value"] = obj
    return out


def odata_values(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("value", "Value", "items", "Items", "results", "Results"):
            if isinstance(payload.get(key), list):
                return [x for x in payload[key] if isinstance(x, dict)]
        # alguns endpoints podem devolver um único registro
        if payload:
            return [payload]
    return []


# =========================
# Cliente HTTP
# =========================

class HttpClient:
    def __init__(self, timeout: int = TIMEOUT):
        self.timeout = timeout
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": USER_AGENT})

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        last_exc: Optional[Exception] = None
        for attempt in range(1, RETRIES + 1):
            try:
                resp = self.s.get(url, timeout=self.timeout, **kwargs)
                if resp.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                return resp
            except Exception as exc:  # pragma: no cover - rede depende do ambiente do usuário
                last_exc = exc
                if attempt == RETRIES:
                    raise
                time.sleep(SLEEP_RETRY * attempt)
        assert last_exc is not None
        raise last_exc

    def get_json(self, url: str, **kwargs: Any) -> Any:
        resp = self.get(url, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def get_bytes(self, url: str, **kwargs: Any) -> bytes:
        resp = self.get(url, **kwargs)
        resp.raise_for_status()
        return resp.content


# =========================
# Estruturas de dados
# =========================

@dataclass
class InstitutionRef:
    input_value: str
    institution_name: Optional[str] = None
    cnpj: Optional[str] = None
    cnpj8: Optional[str] = None
    ticker: Optional[str] = None
    match_score: Optional[float] = None


@dataclass
class IndicatorResult:
    input_value: str
    institution_name: Optional[str]
    cnpj: Optional[str]
    cnpj8: Optional[str]
    quarter: str

    lcr: Optional[float] = None
    nsfr: Optional[float] = None
    hqla: Optional[float] = None
    net_cash_outflows_30d: Optional[float] = None
    asf: Optional[float] = None
    rsf: Optional[float] = None

    lcr_source: Optional[str] = None
    nsfr_source: Optional[str] = None
    hqla_source: Optional[str] = None
    net_cash_outflows_source: Optional[str] = None
    asf_source: Optional[str] = None
    rsf_source: Optional[str] = None

    proxy_lcr_bs: Optional[float] = None
    proxy_nsfr_bs: Optional[float] = None
    proxy_liquid_assets: Optional[float] = None
    proxy_short_term_funding: Optional[float] = None
    proxy_stable_funding: Optional[float] = None
    proxy_required_stable_funding: Optional[float] = None
    proxy_source: Optional[str] = None
    proxy_notes: Optional[str] = None

    observations: Optional[str] = None


# =========================
# Resolução de instituições
# =========================

class InstitutionResolver:
    def __init__(self, http: HttpClient, debug: bool = False):
        self.http = http
        self.debug = debug
        self._ifdata_cache: Optional[List[Dict[str, Any]]] = None

    def _extract_registry_rows(self, rows: List[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
        cleaned: List[Dict[str, Any]] = []
        for row in rows:
            flat = flatten(row)
            name = None
            cnpj = None
            for k, v in flat.items():
                kn = norm_text(k)
                if name is None and "nome" in kn and any(tok in kn for tok in ["instit", "conglomer", "razao", "empresa", "fantasia"]):
                    sv = str(v or "").strip()
                    if sv:
                        name = sv
                if cnpj is None and "cnpj" in kn:
                    d = digits_only(v)
                    if is_plausible_cnpj(d, min_len=8):
                        cnpj = d[:14] if len(d) >= 14 else d
            if not name:
                for k, v in flat.items():
                    kn = norm_text(k)
                    if "nome" in kn:
                        sv = str(v or "").strip()
                        if sv:
                            name = sv
                            break
            if name or cnpj:
                cleaned.append({
                    "name": name,
                    "name_norm": norm_text(name),
                    "cnpj": cnpj,
                    "cnpj8": cnpj[:8] if is_acceptable_cnpj8(cnpj) else None,
                    "source": source,
                    "raw": row,
                })
        return cleaned

    def _load_registry_from_instituicoes_funcionamento(self) -> List[Dict[str, Any]]:
        merged: List[Dict[str, Any]] = []
        for url in INSTITUICOES_FUNCIONAMENTO_RESOURCES:
            try:
                payload = self.http.get_json(url)
                rows = odata_values(payload)
                part = self._extract_registry_rows(rows, source=url)
                merged.extend(part)
                if self.debug:
                    eprint(f"[debug] cadastro de funcionamento carregado: {len(part)} linhas de {url}")
            except Exception as exc:
                if self.debug:
                    eprint(f"[debug] falha em cadastro de funcionamento {url}: {exc}")
        return merged

    def _load_registry_from_ifdata(self) -> List[Dict[str, Any]]:
        urls = [
            f"{IFDATA_CADASTRO}?$format=json",
            f"{IFDATA_CADASTRO}?$format=json&$top=100000",
        ]
        for url in urls:
            try:
                payload = self.http.get_json(url)
                rows = odata_values(payload)
                part = self._extract_registry_rows(rows, source=url)
                if self.debug:
                    eprint(f"[debug] IFData cadastro carregado: {len(part)} linhas de {url}")
                if part:
                    return part
            except Exception as exc:
                if self.debug:
                    eprint(f"[debug] falha em IFData cadastro {url}: {exc}")
        return []

    def _dedupe_registry(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for r in rows:
            key = None
            if r.get("cnpj"):
                key = f"cnpj:{r['cnpj']}"
            elif r.get("name_norm"):
                key = f"name:{r['name_norm']}"
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(r)
        return out

    def _load_ifdata_registry(self) -> List[Dict[str, Any]]:
        if self._ifdata_cache is not None:
            return self._ifdata_cache

        merged: List[Dict[str, Any]] = []
        merged.extend(self._load_registry_from_instituicoes_funcionamento())
        merged.extend(self._load_registry_from_ifdata())
        cleaned = self._dedupe_registry(merged)

        self._ifdata_cache = cleaned
        if self.debug:
            eprint(f"[debug] cadastro consolidado: {len(cleaned)} instituições/conglomerados")
        return cleaned

    def _find_by_cnpj(self, value: str) -> InstitutionRef:
        d = digits_only(value)
        rows = self._load_ifdata_registry()
        if len(d) >= 14:
            exact = [r for r in rows if r.get("cnpj") == d[:14]]
            if exact:
                r = exact[0]
                return InstitutionRef(value, r.get("name"), r.get("cnpj"), r.get("cnpj8"), None, 1.0)
        if len(d) >= 8:
            exact8 = [r for r in rows if r.get("cnpj8") == d[:8]]
            if exact8:
                # escolhe o primeiro; para Pilar 3 normalmente basta o CNPJ completo disponível no cadastro
                r = exact8[0]
                return InstitutionRef(value, r.get("name"), r.get("cnpj"), r.get("cnpj8"), None, 1.0)
        cnpj = d[:14] if len(d) >= 14 and any(ch != "0" for ch in d[:14]) else None
        cnpj8 = d[:8] if len(d) >= 8 else None
        return InstitutionRef(value, None, cnpj, cnpj8, None, None)

    def _search_brapi_name(self, ticker: str, token: Optional[str]) -> Optional[str]:
        if not token:
            return None
        urls_and_kwargs = [
            (BRAPI_QUOTE_URL.format(ticker=ticker.upper()), {"headers": {"Authorization": f"Bearer {token}"}}),
            (BRAPI_QUOTE_URL.format(ticker=ticker.upper()) + f"?token={quote(token)}", {}),
        ]
        for url, kwargs in urls_and_kwargs:
            try:
                payload = self.http.get_json(url, **kwargs)
                results = payload.get("results") if isinstance(payload, dict) else None
                if isinstance(results, list) and results:
                    row = results[0]
                    for key in ("longName", "shortName", "companyName"):
                        if row.get(key):
                            return str(row[key]).strip()
            except Exception as exc:
                if self.debug:
                    eprint(f"[debug] BRAPI falhou para {ticker} em {url}: {exc}")
        return None

    def _find_by_name(self, value: str) -> InstitutionRef:
        target = normalize_alias_name(value)
        exact_name_aliases = {
            "banco do brasil": "banco do brasil s a",
            "bb": "banco do brasil s a",
            "banco bradesco": "banco bradesco s a",
            "bradesco": "banco bradesco s a",
            "banco santander brasil": "banco santander brasil s a",
            "santander": "banco santander brasil s a",
            "banco abc brasil": "banco abc brasil s a",
            "itau unibanco": "itau unibanco s a",
        }
        exact_cnpj_aliases = {
            "banco do brasil s a": ("00000000000191", "00000000"),
            "banco bradesco s a": ("60746948000112", "60746948"),
            "banco santander brasil s a": ("90400888000142", "90400888"),
        }
        target = exact_name_aliases.get(target, target)
        rows = self._load_ifdata_registry()
        if not target:
            return InstitutionRef(value)
        if not rows:
            if target in exact_cnpj_aliases:
                alias_cnpj, alias_cnpj8 = exact_cnpj_aliases[target]
                return InstitutionRef(value, target.upper().replace(" S A", " S.A."), alias_cnpj, alias_cnpj8, None, 9.5)
            return InstitutionRef(value)

        target_core = canonical_name_core(target)
        exact_core_matches = [r for r in rows if canonical_name_core(r.get("name_norm") or "") == target_core]
        if exact_core_matches:
            exact_core_matches.sort(
                key=lambda r: (
                    source_priority(str(r.get("source") or "")),
                    1 if is_acceptable_cnpj8(r.get("cnpj")) or is_acceptable_cnpj8(r.get("cnpj8")) else 0,
                    1 if is_plausible_cnpj(r.get("cnpj"), min_len=14) else 0,
                    len(r.get("name_norm") or ""),
                ),
                reverse=True,
            )
            best = exact_core_matches[0]
            best_cnpj = best.get("cnpj")
            best_cnpj8 = best.get("cnpj8") or (best_cnpj[:8] if is_acceptable_cnpj8(best_cnpj) else None)
            if not best_cnpj8 and target in exact_cnpj_aliases:
                alias_cnpj, alias_cnpj8 = exact_cnpj_aliases[target]
                best_cnpj = best_cnpj or alias_cnpj
                best_cnpj8 = alias_cnpj8
            return InstitutionRef(value, best.get("name"), best_cnpj, best_cnpj8, None, 9.9999)

        target_tokens = set(target.split())
        target_core_tokens = set(target_core.split())
        wants_bank = any(tok in target_tokens for tok in {"banco", "bank", "bradesco", "santander", "itau", "unibanco", "brasil", "btg", "bb"})
        wants_coop = "cooperativa" in target_tokens or "credito" in target_tokens

        scored: List[Tuple[float, Dict[str, Any]]] = []
        for r in rows:
            name_norm = r.get("name_norm") or ""
            if not name_norm:
                continue

            candidate_core = canonical_name_core(name_norm)
            candidate_tokens = set(name_norm.split())
            candidate_core_tokens = set(candidate_core.split())

            ratio = difflib.SequenceMatcher(None, target, name_norm).ratio()
            if target == name_norm:
                ratio = 1.0
            elif target in name_norm or name_norm in target:
                ratio = max(ratio, 0.92)

            if target_core and candidate_core == target_core:
                ratio += 0.35
            elif target_core and target_core in candidate_core:
                ratio += 0.12
            elif len(target_core.split()) >= 3 and target_core_tokens and target_core_tokens.issubset(candidate_core_tokens):
                ratio -= 0.18

            overlap = len(target_tokens & candidate_tokens)
            if target_tokens:
                ratio += 0.20 * overlap / max(len(target_tokens), 1)

            generic = {"banco", "bank", "s", "a", "sa", "do", "da", "de", "e", "the"}
            extra_tokens = {t for t in candidate_tokens - target_tokens if t not in generic}
            ratio -= 0.14 * len(extra_tokens)

            source = str(r.get("source") or "")
            ratio += source_priority(source)

            if wants_bank:
                if "banco" in candidate_tokens:
                    ratio += 0.08
                for bad in ("corretora", "distribuidora", "cambio", "titulos", "valores", "mobiliarios", "dvm", "credito", "financiamento", "investimento", "institucional"):
                    if bad in candidate_tokens:
                        ratio -= 0.10
            if wants_coop and "cooperativa" in candidate_tokens:
                ratio += 0.08

            cnpj = r.get("cnpj")
            if cnpj and len(digits_only(cnpj)) >= 14 and any(ch != "0" for ch in digits_only(cnpj)):
                ratio += 0.05
            elif r.get("cnpj8") is not None:
                ratio += 0.01
            else:
                ratio -= 0.20

            scored.append((ratio, r))

        scored.sort(key=lambda x: (x[0], -len(x[1].get("name_norm") or "")), reverse=True)
        if not scored:
            return InstitutionRef(value)

        best_score, best = scored[0]
        cnpj = best.get("cnpj") if best.get("cnpj") else None
        cnpj8 = best.get("cnpj8") if best.get("cnpj8") else None
        return InstitutionRef(value, best.get("name"), cnpj, cnpj8, None, round(best_score, 4))

    def resolve_one(self, value: str, brapi_token: Optional[str] = None) -> InstitutionRef:
        raw = str(value).strip()
        d = digits_only(raw)
        if len(d) in {8, 14}:
            return self._find_by_cnpj(raw)

        # ticker? usa BRAPI só para obter nome e casar com IFData, se disponível
        if re.fullmatch(r"[A-Za-z]{4}\d{1,2}|[A-Za-z]{5}\d{1,2}|[A-Za-z]{4}11|[A-Za-z]{4}34|[A-Za-z]{4}39", raw.strip()):
            guessed_name = self._search_brapi_name(raw, brapi_token)
            if guessed_name:
                out = self._find_by_name(guessed_name)
                out.ticker = raw.upper()
                if out.institution_name or out.cnpj:
                    return out
            alias_name = {
                "ABCB4": "BANCO ABC BRASIL",
                "BBDC3": "BANCO BRADESCO",
                "BBDC4": "BANCO BRADESCO",
                "BBAS3": "BANCO DO BRASIL",
                "BPAC11": "BANCO BTG PACTUAL",
                "ITUB3": "ITAU UNIBANCO",
                "ITUB4": "ITAU UNIBANCO",
                "SANB11": "BANCO SANTANDER BRASIL",
                "SANB3": "BANCO SANTANDER BRASIL",
                "SANB4": "BANCO SANTANDER BRASIL",
            }.get(raw.upper())
            if alias_name:
                out = self._find_by_name(alias_name)
                out.ticker = raw.upper()
                if out.institution_name or out.cnpj:
                    return out
            out = InstitutionRef(raw, ticker=raw.upper())
            return out

        return self._find_by_name(normalize_alias_name(raw))


# =========================
# Pilar 3 / DASFN
# =========================

def build_dasfn_catalog_url(cnpj: str, resource_template: str) -> str:
    # A filtragem por Recurso com barras/chaves tem retornado 400 no DASFN.
    # Por robustez, filtramos só por Api e CNPJ, e refinamos o recurso localmente.
    filter_str = f"Api eq 'pilar3' and CnpjInstituicao eq '{cnpj}'"
    return f"{DASFN_BASE}?$filter={quote(filter_str, safe="'(){}")}&$format=json"


def pick_field(flat: Dict[str, Any], predicates: Sequence[str]) -> Optional[Any]:
    for key, value in flat.items():
        kn = norm_text(key)
        if all(p in kn for p in predicates):
            return value
    return None


def extract_catalog_rows(payload: Any) -> List[Dict[str, Any]]:
    rows = odata_values(payload)
    out: List[Dict[str, Any]] = []
    for row in rows:
        flat = flatten(row)
        url = None
        versao = None
        nome = None
        cnpj = None
        recurso = None
        for k, v in flat.items():
            kn = norm_text(k)
            if url is None and ("url" in kn or kn.endswith("uri")) and isinstance(v, str) and v.startswith("http"):
                url = v
            if versao is None and "versao" in kn:
                versao = str(v)
            if nome is None and "nome" in kn and "instit" in kn:
                nome = str(v)
            if cnpj is None and "cnpj" in kn:
                d = digits_only(v)
                if len(d) >= 14:
                    cnpj = d[:14]
            if recurso is None and "recurso" in kn:
                recurso = str(v)
        if url:
            out.append({
                "url": url,
                "versao": versao or "0",
                "institution_name": nome,
                "cnpj": cnpj,
                "resource": recurso,
                "raw": row,
            })
    out.sort(key=lambda x: semver_key(x.get("versao") or "0"), reverse=True)
    return out


def choose_best_catalog_url(rows: List[Dict[str, Any]], resource_template: Optional[str] = None) -> Optional[str]:
    if not rows:
        return None
    filtered = rows
    if resource_template:
        filtered = [r for r in rows if norm_text(r.get("resource")) == norm_text(resource_template)] or rows
    filtered.sort(key=lambda x: semver_key(x.get("versao") or "0"), reverse=True)
    return filtered[0].get("url")


def row_line_and_desc(row: Dict[str, Any]) -> Tuple[Optional[int], str]:
    flat = flatten(row)
    line_val: Optional[int] = None
    desc = ""

    for k, v in flat.items():
        kn = norm_text(k)
        if line_val is None and "linha" in kn:
            d = digits_only(v)
            if d:
                line_val = int(d)
        if not desc and any(x in kn for x in ["descricao", "descr", "titulo", "nome"]):
            desc = str(v or "").strip()

    if line_val is None and desc:
        m = re.match(r"\s*(\d{1,3})\b", desc)
        if m:
            line_val = int(m.group(1))
    return line_val, desc


def choose_numeric_value(row: Dict[str, Any], table: str) -> Optional[float]:
    flat = flatten(row)

    ignored_tokens = [
        "linha", "descricao", "descr", "titulo", "nome", "trimestre", "semestre", "ano", "cnpj", "instit", "data", "versao",
        "recurso", "url"
    ]
    candidates: List[Tuple[int, float]] = []

    for k, v in flat.items():
        kn = norm_text(k)
        if any(tok in kn for tok in ignored_tokens):
            continue
        val = parse_decimal(v)
        if val is None:
            continue
        score = 0
        if table == "km1":
            score += 5
            if kn in {"a", "valor", "valor a", "coluna a"}:
                score += 5
        elif table == "liq1":
            if "ajust" in kn:
                score += 20
            if "ponder" in kn:
                score += 10
            if kn in {"valor total ajustado", "valor total ajustado r mil", "a", "b", "valor"}:
                score += 5
        elif table == "liq2":
            if "apos" in kn and "ponder" in kn:
                score += 20
            if kn.endswith(" e") or kn == "e":
                score += 10
            if "valor" in kn:
                score += 5
        candidates.append((score, val))

    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], abs(x[1])), reverse=True)
    return candidates[0][1]


def extract_metric_from_rows(rows: List[Dict[str, Any]], table: str, wanted_lines: Dict[int, str], wanted_descs: Dict[str, str]) -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {v: None for v in set(wanted_lines.values()) | set(wanted_descs.values())}
    for row in rows:
        line, desc = row_line_and_desc(row)
        value = choose_numeric_value(row, table)
        if value is None:
            continue

        if line is not None and line in wanted_lines and out[wanted_lines[line]] is None:
            out[wanted_lines[line]] = value
            continue

        desc_n = norm_text(desc)
        for token, label in wanted_descs.items():
            if token in desc_n and out[label] is None:
                out[label] = value
    return out


def fetch_pillar3_table(http: HttpClient, cnpj: str, resource_template: str, quarter: str, debug: bool = False) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    url = build_dasfn_catalog_url(cnpj, resource_template)
    try:
        payload = http.get_json(url)
    except Exception as exc:
        if debug:
            eprint(f"[debug] falha catálogo DASFN para {cnpj} {resource_template}: {exc}")
        return None, None
    catalog_rows = extract_catalog_rows(payload)
    chosen_url = choose_best_catalog_url(catalog_rows, resource_template=resource_template)
    if chosen_url and "{trimestre}" in chosen_url:
        chosen_url = chosen_url.replace("{trimestre}", quarter)
    if debug:
        matched = [r for r in catalog_rows if norm_text(r.get("resource")) == norm_text(resource_template)]
        eprint(f"[debug] recurso {resource_template} | catálogo total: {len(catalog_rows)} | casados: {len(matched)} | URL: {chosen_url}")
    if not chosen_url:
        return None, None
    try:
        payload_table = http.get_json(chosen_url)
    except Exception as exc:
        if debug:
            eprint(f"[debug] falha ao baixar tabela {resource_template}: {exc}")
        return None, chosen_url
    rows = odata_values(payload_table)
    return rows, chosen_url


def get_direct_metrics(http: HttpClient, inst: InstitutionRef, quarter: str, debug: bool = False) -> IndicatorResult:
    result = IndicatorResult(
        input_value=inst.input_value,
        institution_name=inst.institution_name,
        cnpj=inst.cnpj,
        cnpj8=inst.cnpj8,
        quarter=quarter,
    )
    if not inst.cnpj:
        result.observations = "Instituição não resolvida para CNPJ completo; pulando consulta regulatória direta."
        return result

    # LIQ1
    liq1_rows, liq1_url = fetch_pillar3_table(http, inst.cnpj, "/liq1/{trimestre}", quarter=quarter, debug=debug)
    if liq1_rows:
        m = extract_metric_from_rows(
            liq1_rows,
            table="liq1",
            wanted_lines={21: "hqla", 22: "net_cash_outflows_30d", 23: "lcr"},
            wanted_descs={
                "total hqla": "hqla",
                "saidas liquidas de caixa": "net_cash_outflows_30d",
                "lcr": "lcr",
            },
        )
        if m.get("hqla") is not None:
            result.hqla = m["hqla"]
            result.hqla_source = f"Pilar3-LIQ1|{liq1_url}"
        if m.get("net_cash_outflows_30d") is not None:
            result.net_cash_outflows_30d = m["net_cash_outflows_30d"]
            result.net_cash_outflows_source = f"Pilar3-LIQ1|{liq1_url}"
        if m.get("lcr") is not None:
            result.lcr = m["lcr"]
            result.lcr_source = f"Pilar3-LIQ1|{liq1_url}"

    # LIQ2
    liq2_rows, liq2_url = fetch_pillar3_table(http, inst.cnpj, "/liq2/{trimestre}", quarter=quarter, debug=debug)
    if liq2_rows:
        m = extract_metric_from_rows(
            liq2_rows,
            table="liq2",
            wanted_lines={14: "asf", 33: "rsf", 34: "nsfr"},
            wanted_descs={
                "total de recursos estaveis disponiveis": "asf",
                "total de recursos estaveis requeridos": "rsf",
                "nsfr": "nsfr",
            },
        )
        if m.get("asf") is not None:
            result.asf = m["asf"]
            result.asf_source = f"Pilar3-LIQ2|{liq2_url}"
        if m.get("rsf") is not None:
            result.rsf = m["rsf"]
            result.rsf_source = f"Pilar3-LIQ2|{liq2_url}"
        if m.get("nsfr") is not None:
            result.nsfr = m["nsfr"]
            result.nsfr_source = f"Pilar3-LIQ2|{liq2_url}"

    # KM1 como fallback regulatório resumido
    km1_rows, km1_url = fetch_pillar3_table(http, inst.cnpj, "/km1/{trimestre}", quarter=quarter, debug=debug)
    if km1_rows:
        m = extract_metric_from_rows(
            km1_rows,
            table="km1",
            wanted_lines={15: "hqla", 16: "net_cash_outflows_30d", 17: "lcr", 18: "asf", 19: "rsf", 20: "nsfr"},
            wanted_descs={
                "total de ativos de alta liquidez": "hqla",
                "saidas liquidas de caixa": "net_cash_outflows_30d",
                "lcr": "lcr",
                "recursos estaveis disponiveis": "asf",
                "recursos estaveis requeridos": "rsf",
                "nsfr": "nsfr",
            },
        )
        if result.hqla is None and m.get("hqla") is not None:
            result.hqla = m["hqla"]
            result.hqla_source = f"Pilar3-KM1|{km1_url}"
        if result.net_cash_outflows_30d is None and m.get("net_cash_outflows_30d") is not None:
            result.net_cash_outflows_30d = m["net_cash_outflows_30d"]
            result.net_cash_outflows_source = f"Pilar3-KM1|{km1_url}"
        if result.lcr is None and m.get("lcr") is not None:
            result.lcr = m["lcr"]
            result.lcr_source = f"Pilar3-KM1|{km1_url}"
        if result.asf is None and m.get("asf") is not None:
            result.asf = m["asf"]
            result.asf_source = f"Pilar3-KM1|{km1_url}"
        if result.rsf is None and m.get("rsf") is not None:
            result.rsf = m["rsf"]
            result.rsf_source = f"Pilar3-KM1|{km1_url}"
        if result.nsfr is None and m.get("nsfr") is not None:
            result.nsfr = m["nsfr"]
            result.nsfr_source = f"Pilar3-KM1|{km1_url}"

    return result


# =========================
# Balancete / proxies
# =========================

def decode_csv_from_zip(blob: bytes) -> List[Dict[str, Any]]:
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith((".csv", ".txt"))]
        if not names:
            raise ValueError("ZIP sem arquivo CSV/TXT interno.")
        with zf.open(names[0]) as f:
            raw = f.read()
    text = None
    for enc in ("utf-8-sig", "latin1", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("latin1", errors="replace")

    lines = text.splitlines()
    header_idx = 0
    for i, line in enumerate(lines[:50]):
        ln = norm_text(line)
        if ("conta" in ln and ("saldo" in ln or "valor" in ln)) or ("nome" in ln and "instit" in ln):
            header_idx = i
            break
    text2 = "\n".join(lines[header_idx:])
    sample = text2[:4096]
    dialect = choose_csv_dialect(sample)
    reader = csv.DictReader(io.StringIO(text2), dialect=dialect)
    return [r for r in reader if any((str(v).strip() for v in r.values()))]


def identify_balancete_fields(rows: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    if not rows:
        return {"conta": None, "nome_conta": None, "saldo": None, "cnpj": None, "nome_inst": None, "data": None}
    cols = list(rows[0].keys())
    mapping: Dict[str, Optional[str]] = {"conta": None, "nome_conta": None, "saldo": None, "cnpj": None, "nome_inst": None, "data": None}
    for col in cols:
        cn = norm_text(col)
        if mapping["conta"] is None and cn in {"conta", "cod conta", "codigo conta"}:
            mapping["conta"] = col
        if mapping["nome_conta"] is None and (("nome" in cn and "conta" in cn) or cn == "descricao conta"):
            mapping["nome_conta"] = col
        if mapping["saldo"] is None and ("saldo" in cn or cn in {"valor", "vlr", "montante"}):
            mapping["saldo"] = col
        if mapping["cnpj"] is None and "cnpj" in cn:
            mapping["cnpj"] = col
        if mapping["nome_inst"] is None and "nome" in cn and "instit" in cn:
            mapping["nome_inst"] = col
        if mapping["data"] is None and cn == "data":
            mapping["data"] = col
    return mapping


def account_depth(code: str) -> int:
    if not code:
        return 999
    if "." in code:
        return len([x for x in code.split(".") if x])
    code_d = re.sub(r"\D+", "", code)
    return max(1, len(code_d) // 2)


def best_group_value(rows: List[Dict[str, Any]], include: Sequence[str], exclude: Sequence[str] = ()) -> Tuple[float, List[str]]:
    pats_in = [re.compile(p, flags=re.I) for p in include]
    pats_ex = [re.compile(p, flags=re.I) for p in exclude]
    matches: List[Tuple[int, float, str, str]] = []
    for r in rows:
        name = str(r.get("_nome_conta") or "")
        name_norm = norm_text(name)
        code = str(r.get("_conta") or "")
        if not name_norm:
            continue
        if not all(p.search(name_norm) for p in pats_in):
            continue
        if any(p.search(name_norm) for p in pats_ex):
            continue
        saldo = r.get("_saldo")
        if saldo is None:
            continue
        matches.append((account_depth(code), float(saldo), name, code))

    if not matches:
        return 0.0, []
    # evita dupla contagem: escolhe a rubrica mais agregada (menor profundidade) e maior valor absoluto
    matches.sort(key=lambda x: (x[0], -abs(x[1])))
    best_depth = matches[0][0]
    narrowed = [m for m in matches if m[0] == best_depth]
    narrowed.sort(key=lambda x: abs(x[1]), reverse=True)
    best = narrowed[0]
    return best[1], [f"{best[3]} | {best[2]}"]


def preprocess_balancete_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    m = identify_balancete_fields(rows)
    out: List[Dict[str, Any]] = []
    for r in rows:
        saldo = parse_decimal(r.get(m["saldo"])) if m["saldo"] else None
        if saldo is None:
            continue
        out.append({
            **r,
            "_conta": str(r.get(m["conta"])) if m["conta"] else "",
            "_nome_conta": str(r.get(m["nome_conta"])) if m["nome_conta"] else "",
            "_saldo": float(saldo),
            "_cnpj": digits_only(r.get(m["cnpj"])) if m["cnpj"] else None,
            "_nome_inst": str(r.get(m["nome_inst"])) if m["nome_inst"] else None,
            "_data": str(r.get(m["data"])) if m["data"] else None,
        })
    return out


def compute_proxies_from_balancete(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Ativos líquidos
    disponibilidade, used_disp = best_group_value(rows, [r"disponibil"])
    interliq, used_interliq = best_group_value(rows, [r"aplica", r"interfinanceir", r"liquidez"])
    tvm, used_tvm = best_group_value(rows, [r"tit", r"valor mobili|valores mobili|tvm"])

    # Funding / passivos
    depositos, used_dep = best_group_value(rows, [r"deposit"])
    mercado_aberto, used_ma = best_group_value(rows, [r"mercado aberto|revenda|compromissad"])
    atacado_1, used_at1 = best_group_value(rows, [r"aceites|emissao de tit|emissao de tit|letras|debent"])
    atacado_2, used_at2 = best_group_value(rows, [r"emprestimos|repasses"])
    pl, used_pl = best_group_value(rows, [r"patrimonio liquido|patrim l quido|patrimonio liqu"])

    # Ativos menos líquidos
    credito, used_cred = best_group_value(rows, [r"operac", r"credito"], exclude=[r"cessao", r"coobrigacao"])
    permanente, used_perm = best_group_value(rows, [r"permanente|imobilizado|intangivel|investimento"])

    liquid_assets = disponibilidade + interliq + 0.50 * max(tvm, 0.0)
    short_term_funding = max(depositos, 0.0) + max(mercado_aberto, 0.0) + max(atacado_1, 0.0) + max(atacado_2, 0.0)
    stable_funding = max(pl, 0.0) + 0.90 * max(depositos, 0.0) + 0.50 * (max(mercado_aberto, 0.0) + max(atacado_1, 0.0) + max(atacado_2, 0.0))
    required_stable_funding = 0.00 * max(disponibilidade, 0.0) + 0.15 * max(tvm, 0.0) + 0.50 * max(interliq, 0.0) + 0.85 * max(credito, 0.0) + 1.00 * max(permanente, 0.0)

    proxy_lcr_bs = 100.0 * liquid_assets / max(short_term_funding, EPS)
    proxy_nsfr_bs = 100.0 * stable_funding / max(required_stable_funding, EPS)

    notes_parts = []
    if used_disp:
        notes_parts.append("Disponibilidades=" + "; ".join(used_disp))
    if used_interliq:
        notes_parts.append("Aplicações interfinanceiras=" + "; ".join(used_interliq))
    if used_tvm:
        notes_parts.append("TVM=" + "; ".join(used_tvm))
    if used_dep:
        notes_parts.append("Depósitos=" + "; ".join(used_dep))
    if used_ma:
        notes_parts.append("Mercado aberto=" + "; ".join(used_ma))
    if used_at1 or used_at2:
        notes_parts.append("Funding atacado=" + "; ".join(used_at1 + used_at2))
    if used_pl:
        notes_parts.append("PL=" + "; ".join(used_pl))
    if used_cred:
        notes_parts.append("Crédito=" + "; ".join(used_cred))
    if used_perm:
        notes_parts.append("Permanente=" + "; ".join(used_perm))

    return {
        "proxy_lcr_bs": proxy_lcr_bs,
        "proxy_nsfr_bs": proxy_nsfr_bs,
        "proxy_liquid_assets": liquid_assets,
        "proxy_short_term_funding": short_term_funding,
        "proxy_stable_funding": stable_funding,
        "proxy_required_stable_funding": required_stable_funding,
        "proxy_notes": " | ".join(notes_parts),
    }


def fetch_balancete_proxy(http: HttpClient, inst: InstitutionRef, quarter: str, debug: bool = False) -> Dict[str, Any]:
    if not inst.cnpj8:
        return {"observations": "Instituição sem CNPJ8 para consulta do balancete."}

    urls = []
    base_upper = BALANCETE_URL_TEMPLATE.format(yyyymm=quarter, cnpj8=inst.cnpj8)
    urls.append(base_upper)
    if base_upper.endswith('.ZIP'):
        urls.append(base_upper[:-4] + '.zip')

    last_exc = None
    for url in urls:
        if debug:
            eprint(f"[debug] balancete URL: {url}")
        try:
            blob = http.get_bytes(url)
            rows_raw = decode_csv_from_zip(blob)
            rows = preprocess_balancete_rows(rows_raw)
            if inst.cnpj8:
                filtered = [r for r in rows if (r.get("_cnpj") or "")[:8] == inst.cnpj8]
                if filtered:
                    rows = filtered
            if not rows:
                return {"observations": f"Balancete baixado em {url}, mas sem linhas utilizáveis para a instituição."}
            proxy = compute_proxies_from_balancete(rows)
            proxy["proxy_source"] = f"BCB-Balancete4010|{url}"
            return proxy
        except Exception as exc:  # pragma: no cover - depende da disponibilidade remota
            last_exc = exc
            if debug:
                eprint(f"[debug] balancete indisponível para {inst.input_value} em {url}: {exc}")
    return {"observations": f"Falha ao obter balancete 4010 para {inst.cnpj8} em {quarter}: {last_exc}" if last_exc else "Balancete indisponível."}


# =========================
# I/O
# =========================

def load_inputs(args: argparse.Namespace) -> List[str]:
    values: List[str] = []
    for attr in ["institutions", "cnpjs", "tickers"]:
        raw = getattr(args, attr, None)
        if raw:
            parts = [x.strip() for x in re.split(r"[;,\n]+", raw) if x.strip()]
            values.extend(parts)

    if args.input:
        with open(args.input, "r", encoding="utf-8-sig", newline="") as f:
            sample = f.read(4096)
            f.seek(0)
            dialect = choose_csv_dialect(sample)
            reader = csv.DictReader(f, dialect=dialect)
            for row in reader:
                for key in ["institution", "instituicao", "nome", "cnpj", "cnpj8", "ticker"]:
                    if key in row and str(row[key]).strip():
                        values.append(str(row[key]).strip())
                        break
    # remove duplicados preservando ordem
    seen = set()
    out = []
    for v in values:
        key = norm_text(v) if not digits_only(v) else digits_only(v)
        if key not in seen:
            seen.add(key)
            out.append(v)
    return out


def save_csv(rows: List[IndicatorResult], path: str) -> None:
    if not rows:
        return
    data = [asdict(r) for r in rows]
    fieldnames = list(data[0].keys())
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(data)


def print_summary(rows: List[IndicatorResult]) -> None:
    header = [
        "instituicao", "cnpj", "quarter", "lcr", "nsfr", "proxy_lcr_bs", "proxy_nsfr_bs", "lcr_source", "nsfr_source"
    ]
    print(";".join(header))
    for r in rows:
        print(";".join([
            str(r.institution_name or r.input_value or ""),
            str(r.cnpj or ""),
            str(r.quarter or ""),
            "" if r.lcr is None else f"{r.lcr:.6f}",
            "" if r.nsfr is None else f"{r.nsfr:.6f}",
            "" if r.proxy_lcr_bs is None else f"{r.proxy_lcr_bs:.6f}",
            "" if r.proxy_nsfr_bs is None else f"{r.proxy_nsfr_bs:.6f}",
            str(r.lcr_source or ""),
            str(r.nsfr_source or ""),
        ]))


# =========================
# Main
# =========================

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Obtém LCR/NSFR diretos do BCB e gera proxies quando necessário.")
    p.add_argument("--institutions", help="Lista separada por ; ou , com nomes de instituições.")
    p.add_argument("--cnpjs", help="Lista separada por ; ou , com CNPJs (8 ou 14 dígitos).")
    p.add_argument("--tickers", help="Lista separada por ; ou , com tickers (opcional, usa BRAPI para apoiar a resolução do nome).")
    p.add_argument("--input", help="CSV de entrada com colunas institution/nome/cnpj/cnpj8/ticker.")
    p.add_argument("--quarter", help="Trimestre único, lista ou faixa. Exemplos: 202412 | 2024Q4 | 202403,202406,202409,202412 | 2023Q1:2024Q4.")
    p.add_argument("--quarters", help="Alias explícito de --quarter para listas/faixas de trimestres.")
    p.add_argument("--out", default="lcr_nsfr_resultado.csv", help="Arquivo CSV de saída.")
    p.add_argument("--brapi-token", default=os.getenv("BRAPI_TOKEN"), help="Token opcional da BRAPI (ou variável de ambiente BRAPI_TOKEN).")
    p.add_argument("--debug", action="store_true", help="Mostra logs de depuração no stderr.")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    quarters = parse_quarters(args.quarter, args.quarters)
    inputs = load_inputs(args)
    if not inputs:
        eprint("Nenhuma instituição informada. Use --institutions, --cnpjs, --tickers ou --input.")
        return 2

    http = HttpClient()
    resolver = InstitutionResolver(http=http, debug=args.debug)

    results: List[IndicatorResult] = []
    total_jobs = len(inputs) * len(quarters)
    eprint(
        f"Processando {len(inputs)} instituição(ões) em {len(quarters)} trimestre(s) "
        f"({total_jobs} combinação(ões))..."
    )
    if args.debug:
        eprint(f"[debug] quarters={quarters}")

    job = 0
    for i, raw in enumerate(inputs, start=1):
        inst = resolver.resolve_one(raw, brapi_token=args.brapi_token)
        if args.debug:
            eprint(f"[debug] resolvido -> nome={inst.institution_name!r} cnpj={inst.cnpj!r} cnpj8={inst.cnpj8!r} score={inst.match_score!r}")

        for quarter in quarters:
            job += 1
            eprint(f"[{job}/{total_jobs}] {raw} | trimestre {quarter}")

            direct = get_direct_metrics(http=http, inst=inst, quarter=quarter, debug=args.debug)

            # Proxy apenas se necessário
            need_proxy = direct.lcr is None or direct.nsfr is None
            if need_proxy:
                proxy = fetch_balancete_proxy(http=http, inst=inst, quarter=quarter, debug=args.debug)
                if proxy:
                    direct.proxy_lcr_bs = proxy.get("proxy_lcr_bs")
                    direct.proxy_nsfr_bs = proxy.get("proxy_nsfr_bs")
                    direct.proxy_liquid_assets = proxy.get("proxy_liquid_assets")
                    direct.proxy_short_term_funding = proxy.get("proxy_short_term_funding")
                    direct.proxy_stable_funding = proxy.get("proxy_stable_funding")
                    direct.proxy_required_stable_funding = proxy.get("proxy_required_stable_funding")
                    direct.proxy_source = proxy.get("proxy_source")
                    direct.proxy_notes = proxy.get("proxy_notes")

                    if direct.lcr is None and direct.proxy_lcr_bs is not None:
                        direct.lcr = direct.proxy_lcr_bs
                        direct.lcr_source = "proxy_contabil"
                    if direct.nsfr is None and direct.proxy_nsfr_bs is not None:
                        direct.nsfr = direct.proxy_nsfr_bs
                        direct.nsfr_source = "proxy_contabil"
                    if proxy.get("observations"):
                        direct.observations = proxy.get("observations")
                elif proxy.get("observations"):
                    direct.observations = proxy.get("observations")

            if direct.lcr is None and direct.nsfr is None and direct.proxy_lcr_bs is None and direct.proxy_nsfr_bs is None and not direct.observations:
                direct.observations = "Sem LCR/NSFR regulatórios e sem proxy contábil. Verifique resolução da instituição/CNPJ, disponibilidade do Pilar 3 e disponibilidade do balancete para o período."

            # Se o indicador regulatório não vier, mantém nas colunas de proxy e deixa claro a diferença
            results.append(direct)

    save_csv(results, args.out)
    print_summary(results)
    eprint(f"CSV salvo em: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())