# baixar_ifdata_raw_instituicao_v2.py
# -*- coding: utf-8 -*-

import argparse
import gzip
import json
import re
import time
import unicodedata
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Set, Tuple

import requests

# Exemplo geral:
# python baixar_ifdata_raw_instituicao_v2.py --out data_raw --start-year 2010 --end-year 2025 --tipo-instituicao 1
# Exemplo filtrando uma IF por nome:
# python baixar_ifdata_raw_instituicao_v2.py --out ifdata --start-year 2010 --end-year 2025 --relatorios 4 --tipo-instituicao 2 --instituicao "Banco do Brasil"
# Exemplo filtrando por CNPJ:
# python 2_baixar_ifdata_raw_instituicao_v2.py --out ifdata --start-year 2014 --end-year 2025 --tipo-instituicao 1 --cnpj 30306294
# Exemplo filtrando por código: 
# python 2_baixar_ifdata_raw_instituicao_v2.py --out ifdata --start-year 2014 --end-year 2025 --tipo-instituicao 1 --codigo-if 208

BASE_URL = "https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata/"
UA = "dissertacao-liquidez-ml/1.1 (raw-downloader)"

# Campos observados/usados com maior frequência em retornos de cadastro/valores.
EXACT_NAME_FIELDS = {
    "NomeInstituicao",
    "NomeInstituicaoFinanceira",
    "Instituicao",
    "InstituicaoFinanceira",
    "Nome",
    "RazaoSocial",
    "DenominacaoSocial",
    "NomeConglomerado",
    "NomeConglomeradoPrudencial",
}

EXACT_ID_FIELDS = {
    "CodigoInstituicao",
    "CodigoIF",
    "Codigo",
    "CodInst",
    "IdInstituicao",
    "CNPJ",
    "Cnpj",
    "CNPJInstituicao",
    "CnpjInstituicao",
    "CNPJConglomerado",
    "CnpjConglomerado",
    "CodigoConglomerado",
}


def iter_anomes(start_year: int, end_year: int, months: List[int]) -> Iterable[int]:
    """Gera AAAAMM para cada mês informado em cada ano no intervalo."""
    for y in range(start_year, end_year + 1):
        for m in months:
            yield y * 100 + m


def normalize_text(value: Any) -> str:
    """Normaliza texto para comparações tolerantes a acentos/caixa."""
    text = str(value or "").strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text)
    return text.casefold()


def only_digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def slugify(value: str) -> str:
    value = normalize_text(value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "instituicao"


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", normalize_text(value))


def looks_like_name_key(key: str) -> bool:
    nk = normalize_key(key)
    if key in EXACT_NAME_FIELDS:
        return True
    return any(p in nk for p in [
        "nomeinstituicao",
        "nomeinstituicaofinanceira",
        "instituicaofinanceira",
        "razaosocial",
        "denominacaosocial",
        "nomeconglomerado",
        "instituicao",
    ])


def looks_like_id_key(key: str) -> bool:
    nk = normalize_key(key)
    if key in EXACT_ID_FIELDS:
        return True
    patterns = [
        "codigoinstituicao",
        "codigoconglomerado",
        "idinstituicao",
        "codinst",
        "codigoif",
        "cnpjinstituicao",
        "cnpjconglomerado",
    ]
    if any(p in nk for p in patterns):
        return True
    if "cnpj" in nk and any(p in nk for p in ["inst", "institu", "conglomer"]):
        return True
    return False


def safe_get_json(
    session: requests.Session,
    url: str,
    params: Optional[Dict] = None,
    timeout: int = 60,
    max_retries: int = 6,
    backoff: float = 1.5,
) -> Dict:
    """GET com retries simples e retorno JSON."""
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            r = session.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            sleep_s = backoff ** (attempt - 1)
            print(f"[WARN] Falha GET (tentativa {attempt}/{max_retries}). Aguardando {sleep_s:.1f}s. Erro: {e}")
            time.sleep(sleep_s)
    raise RuntimeError(f"Falha ao baixar após {max_retries} tentativas. Último erro: {last_err}")


def extract_odata_page(payload: Dict) -> Tuple[List[Dict], Optional[str]]:
    """
    Extrai lista de registros e próximo link (se existir).
    Olinda/BCB geralmente usa 'value' e '@odata.nextLink'.
    """
    records = payload.get("value")
    if records is None:
        d = payload.get("d") or {}
        records = d.get("results") or []

    next_link = payload.get("@odata.nextLink") or payload.get("odata.nextLink")
    if not next_link:
        d = payload.get("d") or {}
        next_link = d.get("__next")
    return records or [], next_link


def odata_to_jsonl_gz(
    session: requests.Session,
    first_url: str,
    first_params: Dict,
    out_path: Path,
    timeout: int,
    max_retries: int,
    backoff: float,
    top: int = 10000,
    sleep: float = 0.0,
) -> int:
    """
    Baixa um recurso OData paginado e grava em jsonl.gz (streaming).
    Retorna o total de registros gravados.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists() and out_path.stat().st_size > 0:
        print(f"[SKIP] Já existe: {out_path}")
        return 0

    total = 0
    url = first_url
    params = dict(first_params)
    params.setdefault("$format", "json")
    params.setdefault("$top", top)

    print(f"[DOWN] {out_path.name}")

    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        while True:
            payload = safe_get_json(
                session, url, params=params, timeout=timeout, max_retries=max_retries, backoff=backoff
            )
            records, next_link = extract_odata_page(payload)

            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            total += len(records)

            if sleep > 0:
                time.sleep(sleep)

            if not next_link:
                break

            url = next_link
            params = None

    print(f"[OK] Registros: {total} -> {out_path}")
    return total


def iter_jsonl_gz(path: Path) -> Iterable[Dict]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def iter_scalar_items(obj: Any, prefix: str = "") -> Iterator[Tuple[str, Any]]:
    """Itera sobre todos os valores escalares de um registro (inclui aninhamentos, se houver)."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_str = f"{prefix}.{key}" if prefix else str(key)
            yield from iter_scalar_items(value, key_str)
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            key_str = f"{prefix}[{idx}]" if prefix else f"[{idx}]"
            yield from iter_scalar_items(value, key_str)
    else:
        yield prefix, obj


def extract_record_signatures(record: Dict) -> Tuple[Set[str], Set[str]]:
    """
    Extrai assinaturas de nomes e identificadores que aparentam pertencer à instituição.
    Usa campos exatos conhecidos e heurísticas defensivas para acomodar variações do schema.
    """
    name_tokens: Set[str] = set()
    id_tokens: Set[str] = set()

    for key, value in record.items():
        if value is None or str(value).strip() == "":
            continue

        if looks_like_name_key(key):
            norm = normalize_text(value)
            if norm:
                name_tokens.add(norm)

        if looks_like_id_key(key):
            text_norm = normalize_text(value)
            digit_norm = only_digits(value)
            if text_norm:
                id_tokens.add(text_norm)
            if digit_norm:
                id_tokens.add(digit_norm)

    return name_tokens, id_tokens


def record_matches_query(record: Dict, instituicao: Optional[str], codigo_if: Optional[str], cnpj: Optional[str]) -> bool:
    """Verifica se o registro de cadastro corresponde à IF desejada."""
    record_names, record_ids = extract_record_signatures(record)

    if instituicao:
        q = normalize_text(instituicao)
        if any(q == name or q in name for name in record_names):
            return True

    if codigo_if:
        q_text = normalize_text(codigo_if)
        q_digits = only_digits(codigo_if)
        if q_text and q_text in record_ids:
            return True
        if q_digits and q_digits in record_ids:
            return True

    if cnpj:
        q_text = normalize_text(cnpj)
        q_digits = only_digits(cnpj)
        if q_text and q_text in record_ids:
            return True
        if q_digits and q_digits in record_ids:
            return True

    return False


def resolve_institution_signature(
    cadastro_path: Path,
    instituicao: Optional[str],
    codigo_if: Optional[str],
    cnpj: Optional[str],
) -> Optional[Dict[str, Set[str]]]:
    """
    Resolve a instituição a partir do cadastro de um AnoMes, retornando assinaturas
    (nomes/ids) para filtrar os arquivos de valores do mesmo período.
    """
    matched_names: Set[str] = set()
    matched_ids: Set[str] = set()
    found = 0

    for rec in iter_jsonl_gz(cadastro_path):
        if record_matches_query(rec, instituicao=instituicao, codigo_if=codigo_if, cnpj=cnpj):
            names, ids = extract_record_signatures(rec)
            matched_names |= names
            matched_ids |= ids
            found += 1

    if not found:
        return None

    return {"names": matched_names, "ids": matched_ids}


def value_matches_target(
    key: str,
    value: Any,
    target_names: Set[str],
    target_ids: Set[str],
    query_norm: str,
) -> bool:
    if value is None:
        return False

    raw = str(value).strip()
    if not raw:
        return False

    text = normalize_text(raw)
    digits = only_digits(raw)

    if target_names:
        if text in target_names:
            return True
        for name in target_names:
            if len(name) >= 4 and (name in text or text in name):
                return True

    if query_norm and len(query_norm) >= 3 and query_norm in text:
        return True

    if target_ids:
        if text in target_ids:
            return True
        if digits and len(digits) >= 8 and digits in target_ids:
            return True
        if looks_like_id_key(key):
            if digits and digits in target_ids:
                return True
            if text in target_ids:
                return True

    return False


def discover_best_match_keys(
    in_path: Path,
    signature: Dict[str, Set[str]],
    instituicao_query: Optional[str],
    sample_limit: int = 2500,
) -> List[str]:
    """
    Descobre, por amostragem, quais chaves do IfDataValores parecem carregar
    a identidade da instituição. Isso evita depender apenas de nomes de campo fixos.
    """
    target_names = set(signature.get("names", set()))
    target_ids = set(signature.get("ids", set()))
    query_norm = normalize_text(instituicao_query) if instituicao_query else ""
    scores: Dict[str, int] = {}
    inspected = 0

    for rec in iter_jsonl_gz(in_path):
        inspected += 1
        for key, value in iter_scalar_items(rec):
            if value is None or str(value).strip() == "":
                continue

            score = 0
            text = normalize_text(value)
            digits = only_digits(value)

            if target_names:
                if text in target_names:
                    score += 8
                elif any(len(name) >= 4 and (name in text or text in name) for name in target_names):
                    score += 5

            if query_norm and len(query_norm) >= 3 and query_norm in text:
                score += 6

            if target_ids:
                if text in target_ids:
                    score += 8
                if digits and len(digits) >= 8 and digits in target_ids:
                    score += 8
                if looks_like_id_key(key) and ((digits and digits in target_ids) or text in target_ids):
                    score += 6

            if looks_like_name_key(key) and score > 0:
                score += 2

            if score > 0:
                scores[key] = scores.get(key, 0) + score

        if inspected >= sample_limit:
            break

    if not scores:
        return []

    best_score = max(scores.values())
    threshold = max(8, int(best_score * 0.5))
    selected = [key for key, score in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0])) if score >= threshold]
    return selected[:6]


def build_value_filter(
    signature: Dict[str, Set[str]],
    instituicao_query: Optional[str],
    preferred_keys: Optional[List[str]] = None,
) -> Callable[[Dict], bool]:
    target_names = set(signature.get("names", set()))
    target_ids = set(signature.get("ids", set()))
    query_norm = normalize_text(instituicao_query) if instituicao_query else ""
    preferred = set(preferred_keys or [])

    def _match(rec: Dict) -> bool:
        scalar_items = list(iter_scalar_items(rec))

        # 1) Se conseguimos descobrir chaves candidatas, prioriza essas chaves.
        if preferred:
            for key, value in scalar_items:
                if key in preferred and value_matches_target(key, value, target_names, target_ids, query_norm):
                    return True

        # 2) Tenta a heurística antiga sobre nomes de campos conhecidos.
        rec_names, rec_ids = extract_record_signatures(rec)
        if target_ids and (rec_ids & target_ids):
            return True
        if target_names and (rec_names & target_names):
            return True
        if query_norm and any(query_norm == name or query_norm in name for name in rec_names):
            return True

        # 3) Fallback robusto: varre todos os valores escalares do registro.
        for key, value in scalar_items:
            if value_matches_target(key, value, target_names, target_ids, query_norm):
                return True

        return False

    return _match


def filter_existing_jsonl_gz(
    in_path: Path,
    out_path: Path,
    record_filter: Callable[[Dict], bool],
    label: str = "Arquivo filtrado",
) -> int:
    """Filtra um jsonl.gz já baixado e grava apenas os registros desejados."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and out_path.stat().st_size > 0:
        print(f"[SKIP] Já existe: {out_path}")
        return 0

    total_read = 0
    written = 0
    with gzip.open(in_path, "rt", encoding="utf-8") as src, gzip.open(out_path, "wt", encoding="utf-8") as dst:
        for line in src:
            line = line.strip()
            if not line:
                continue
            total_read += 1
            rec = json.loads(line)
            if record_filter(rec):
                dst.write(json.dumps(rec, ensure_ascii=False) + "\n")
                written += 1

    print(f"[OK] {label}: {written} (lidos: {total_read}) -> {out_path}")
    return written


def fetch_lista_relatorios(
    session: requests.Session,
    out_dir: Path,
    timeout: int,
    max_retries: int,
    backoff: float,
    sleep: float,
) -> List[Dict]:
    """Baixa a lista de relatórios e salva em JSONL.GZ."""
    url = BASE_URL + "ListaDeRelatorio()"
    out_path = out_dir / "lista_relatorios.jsonl.gz"

    odata_to_jsonl_gz(
        session,
        first_url=url,
        first_params={"$format": "json", "$top": 10000},
        out_path=out_path,
        timeout=timeout,
        max_retries=max_retries,
        backoff=backoff,
        top=10000,
        sleep=sleep,
    )

    return list(iter_jsonl_gz(out_path))


def build_scope_name(args: argparse.Namespace) -> str:
    if args.codigo_if:
        return f"codigo-{slugify(args.codigo_if)}"
    if args.cnpj:
        return f"cnpj-{only_digits(args.cnpj)}"
    if args.instituicao:
        return slugify(args.instituicao)
    return "geral"


def main() -> None:
    ap = argparse.ArgumentParser(description="Downloader RAW do IFData (BCB/Olinda OData).")
    ap.add_argument("--out", type=str, default="data_raw/ifdata", help="Diretório de saída.")
    ap.add_argument("--start-year", type=int, default=2010, help="Ano inicial (inclusive).")
    ap.add_argument("--end-year", type=int, default=2025, help="Ano final (inclusive).")
    ap.add_argument(
        "--months",
        type=int,
        nargs="+",
        default=[3, 6, 9, 12],
        help="Meses (MM) de referência. Padrão: 3 6 9 12 (trimestres).",
    )
    ap.add_argument("--tipo-instituicao", type=int, default=1, help="TipoInstituicao (padrão 1).")
    ap.add_argument(
        "--relatorios",
        type=str,
        nargs="*",
        default=None,
        help="Lista de NumeroRelatorio para baixar (ex: 1 2 3). Se omitido, baixa todos.",
    )
    ap.add_argument("--instituicao", type=str, default=None, help="Nome parcial ou completo da instituição.")
    ap.add_argument("--codigo-if", type=str, default=None, help="Código da instituição no cadastro do IFData.")
    ap.add_argument("--cnpj", type=str, default=None, help="CNPJ da instituição/conglomerado.")
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--max-retries", type=int, default=6)
    ap.add_argument("--backoff", type=float, default=1.5)
    ap.add_argument("--top", type=int, default=100000, help="Tamanho de página ($top).")
    ap.add_argument("--sleep", type=float, default=0.0, help="Pausa (seg) entre requisições.")
    args = ap.parse_args()

    filtering_by_institution = any([args.instituicao, args.codigo_if, args.cnpj])
    scope_name = build_scope_name(args) if filtering_by_institution else "geral"

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept": "application/json"})

    print("[STEP] Baixando ListaDeRelatorio() ...")
    rels = fetch_lista_relatorios(
        session=session,
        out_dir=out_dir,
        timeout=args.timeout,
        max_retries=args.max_retries,
        backoff=args.backoff,
        sleep=args.sleep,
    )

    available_codes = sorted(
        {str(r.get("NumeroRelatorio")) for r in rels if r.get("NumeroRelatorio") is not None},
        key=lambda x: int(x),
    )
    if not available_codes:
        raise RuntimeError("Não consegui extrair NumeroRelatorio da ListaDeRelatorio().")

    if args.relatorios:
        selected = [str(x) for x in args.relatorios]
        missing = sorted(set(selected) - set(available_codes), key=lambda x: int(x))
        if missing:
            print(f"[WARN] Relatórios não encontrados na lista do BCB: {missing}")
        rel_codes = [x for x in selected if x in set(available_codes)]
    else:
        rel_codes = available_codes

    print(f"[INFO] Relatórios selecionados: {len(rel_codes)} (de {len(available_codes)} disponíveis)")
    if filtering_by_institution:
        print(f"[INFO] Modo instituição específica ativado: {scope_name}")
        print("[INFO] Nesta versão, os arquivos RAW completos são usados como cache e o filtro é aplicado depois.")

    print("[STEP] Baixando IfDataCadastro(AnoMes=@AnoMes) ...")
    signatures_by_period: Dict[int, Dict[str, Set[str]]] = {}

    for anomes in iter_anomes(args.start_year, args.end_year, args.months):
        url = BASE_URL + "IfDataCadastro(AnoMes=@AnoMes)"
        full_cadastro_path = out_dir / "cadastro" / f"ifdata_cadastro_{anomes}.jsonl.gz"

        odata_to_jsonl_gz(
            session=session,
            first_url=url,
            first_params={"@AnoMes": anomes, "$format": "json"},
            out_path=full_cadastro_path,
            timeout=args.timeout,
            max_retries=args.max_retries,
            backoff=args.backoff,
            top=args.top,
            sleep=args.sleep,
        )

        if filtering_by_institution:
            signature = resolve_institution_signature(
                cadastro_path=full_cadastro_path,
                instituicao=args.instituicao,
                codigo_if=args.codigo_if,
                cnpj=args.cnpj,
            )
            if signature is None:
                print(f"[WARN] Nenhuma instituição compatível encontrada no cadastro para {anomes}.")
                continue

            signatures_by_period[anomes] = signature
            filtered_cadastro_path = (
                out_dir / "instituicoes" / f"instituicao={scope_name}" / "cadastro" / f"ifdata_cadastro_{anomes}.jsonl.gz"
            )
            cadastro_filter = build_value_filter(signature, args.instituicao)
            filter_existing_jsonl_gz(
                in_path=full_cadastro_path,
                out_path=filtered_cadastro_path,
                record_filter=cadastro_filter,
                label="Cadastro filtrado",
            )

    print("[STEP] Baixando IfDataValores(AnoMes, TipoInstituicao, Relatorio) ...")
    for anomes in iter_anomes(args.start_year, args.end_year, args.months):
        signature = signatures_by_period.get(anomes)
        if filtering_by_institution and signature is None:
            print(f"[WARN] Instituição não encontrada no cadastro para {anomes}; pulando valores desse período.")
            continue

        for rel in rel_codes:
            url = BASE_URL + "IfDataValores(AnoMes=@AnoMes,TipoInstituicao=@TipoInstituicao,Relatorio=@Relatorio)"
            full_out_path = (
                out_dir
                / "valores"
                / f"tipo_instituicao={args.tipo_instituicao}"
                / f"relatorio={rel}"
                / f"ifdata_valores_{anomes}_tipo{args.tipo_instituicao}_rel{rel}.jsonl.gz"
            )

            odata_to_jsonl_gz(
                session=session,
                first_url=url,
                first_params={
                    "@AnoMes": anomes,
                    "@TipoInstituicao": args.tipo_instituicao,
                    "@Relatorio": f"'{rel}'",
                    "$format": "json",
                },
                out_path=full_out_path,
                timeout=args.timeout,
                max_retries=args.max_retries,
                backoff=args.backoff,
                top=args.top,
                sleep=args.sleep,
            )

            if filtering_by_institution:
                preferred_keys = discover_best_match_keys(full_out_path, signature, args.instituicao)
                if preferred_keys:
                    print(f"[INFO] Campos candidatos para identificar a IF em {anomes}/rel{rel}: {preferred_keys}")
                else:
                    print(f"[INFO] Nenhum campo candidato claro em {anomes}/rel{rel}; usando fallback por conteúdo.")

                record_filter = build_value_filter(signature, args.instituicao, preferred_keys=preferred_keys)
                filtered_out_path = (
                    out_dir
                    / "instituicoes"
                    / f"instituicao={scope_name}"
                    / "valores"
                    / f"tipo_instituicao={args.tipo_instituicao}"
                    / f"relatorio={rel}"
                    / f"ifdata_valores_{anomes}_tipo{args.tipo_instituicao}_rel{rel}_{scope_name}.jsonl.gz"
                )
                written = filter_existing_jsonl_gz(
                    in_path=full_out_path,
                    out_path=filtered_out_path,
                    record_filter=record_filter,
                    label="Valores filtrados",
                )
                if written == 0:
                    print(
                        f"[WARN] Nenhum registro compatível em {anomes}/rel{rel}. "
                        "Isso pode indicar que a IF não aparece nesse relatório ou que o schema mudou."
                    )

    print("[DONE] Downloads concluídos (somente download; sem tratamento/ETL).")


if __name__ == "__main__":
    main()
