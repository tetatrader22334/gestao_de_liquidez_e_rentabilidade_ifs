#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extrair_ifdata_contas_v2.py

Extrai contas e instituições selecionadas de arquivos JSONL do IF.Data e gera CSV.
- Streaming linha a linha (bom para arquivos grandes)
- Diagnóstico automático quando "Linhas escritas = 0"
- Opção para ignorar zeros à esquerda em CodInst/Conta

Uso:
  python extrair_ifdata_contas_v2.py -i dados.jsonl -o recorte.csv --instituicoes 00058338 --contas 78182

Diagnóstico (se sair 0, ele imprime um resumo). Você também pode forçar:
  python extrair_ifdata_contas_v2.py ... --diagnostic
  
  Linhas de comando:
  python 9_extrair_ifdata_contas_v2.py -i ifdata/sanity_check/ifdata_valores_201403_tipo1_rel4.jsonl -o ifdata/sanity_check/extracted_rpad6/ext_201403_t1_r4.csv --instituicoes "C0080109"
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple, Union

try:
    import pandas as pd  # opcional: somente para ler listas em csv/xlsx
except Exception:
    pd = None


def _read_lines(path: Union[str, Path]) -> List[str]:
    out: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            v = line.strip()
            if v and not v.startswith("#"):
                out.append(v)
    return out


def _read_list_file(path: Union[str, Path], preferred_cols: Sequence[str]) -> List[str]:
    """
    Lê uma lista de valores a partir de:
      - .txt (1 valor por linha)
      - .csv (tenta colunas em preferred_cols; senão usa a primeira coluna)
      - .xlsx/.xls (idem; primeira planilha)
    """
    path = Path(path)
    ext = path.suffix.lower()

    if ext in (".txt", ".list"):
        return _read_lines(path)

    if pd is None:
        raise RuntimeError(
            "Para ler listas em CSV/XLSX, instale pandas: pip install pandas openpyxl"
        )

    if ext == ".csv":
        df = pd.read_csv(path)
    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    else:
        raise ValueError(f"Extensão não suportada para lista: {path}")

    if df.empty:
        return []

    cols_lower = {c.lower(): c for c in df.columns}
    for c in preferred_cols:
        if c.lower() in cols_lower:
            col = cols_lower[c.lower()]
            return [str(x).strip() for x in df[col].dropna().tolist() if str(x).strip()]

    col0 = df.columns[0]
    return [str(x).strip() for x in df[col0].dropna().tolist() if str(x).strip()]


def _parse_csv_list(s: Optional[str]) -> List[str]:
    if not s:
        return []
    parts = []
    for chunk in s.replace(";", ",").split(","):
        v = chunk.strip()
        if v:
            parts.append(v)
    return parts


def _normalize_str(x: object) -> str:
    if x is None:
        return ""
    return str(x).strip()


def _strip_zeros_if_digits(s: str) -> str:
    """Remove zeros à esquerda apenas se for uma string numérica."""
    s2 = s.strip()
    if s2.isdigit():
        stripped = s2.lstrip("0")
        return stripped if stripped != "" else "0"
    return s2


def _build_match_set(values: Optional[Sequence[str]], strip_zeros: bool) -> Optional[Set[str]]:
    if not values:
        return None
    out: Set[str] = set()
    for v in values:
        vv = str(v).strip()
        if not vv:
            continue
        out.add(vv)
        if strip_zeros:
            out.add(_strip_zeros_if_digits(vv))
    return out or None


def _passes_filters(
    row: Dict[str, object],
    inst_set: Optional[Set[str]],
    conta_set: Optional[Set[str]],
    nome_conta_set: Optional[Set[str]],
    match_mode: str,
    strip_zeros: bool,
) -> bool:
    cod_inst = _normalize_str(row.get("CodInst"))
    conta = _normalize_str(row.get("Conta"))
    nome_coluna = _normalize_str(row.get("NomeColuna")).lower()

    if strip_zeros:
        cod_inst_alt = _strip_zeros_if_digits(cod_inst)
        conta_alt = _strip_zeros_if_digits(conta)
    else:
        cod_inst_alt = cod_inst
        conta_alt = conta

    inst_ok = True if not inst_set else (cod_inst in inst_set or cod_inst_alt in inst_set)

    conta_ok = True
    if conta_set or nome_conta_set:
        by_code = False
        if conta_set:
            by_code = (conta in conta_set) or (conta_alt in conta_set)
        by_name = (nome_coluna in nome_conta_set) if nome_conta_set else False

        if match_mode == "all":
            if conta_set and nome_conta_set:
                conta_ok = by_code and by_name
            else:
                conta_ok = by_code or by_name
        else:
            conta_ok = by_code or by_name

    return inst_ok and conta_ok


def extract_jsonl_to_csv(
    inputs: Sequence[Union[str, Path]],
    output_csv: Union[str, Path],
    inst_set: Optional[Set[str]] = None,
    conta_set: Optional[Set[str]] = None,
    nome_conta_set: Optional[Set[str]] = None,
    match_mode: str = "any",
    strip_zeros: bool = False,
    encoding: str = "utf-8",
    progress_every: int = 200000,
) -> Tuple[int, int]:
    """Retorna (linhas_lidas, linhas_escritas)."""
    output_csv = Path(output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "TipoInstituicao",
        "CodInst",
        "AnoMes",
        "NomeRelatorio",
        "NumeroRelatorio",
        "Grupo",
        "Conta",
        "NomeColuna",
        "DescricaoColuna",
        "Saldo",
    ]

    read_count = 0
    write_count = 0

    with open(output_csv, "w", newline="", encoding="utf-8") as fout:
        writer = csv.DictWriter(fout, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        for inp in inputs:
            inp = Path(inp)
            if not inp.exists():
                raise FileNotFoundError(f"Arquivo não encontrado: {inp}")

            with open(inp, "r", encoding=encoding) as fin:
                for line in fin:
                    line = line.strip()
                    if not line:
                        continue
                    read_count += 1
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if _passes_filters(row, inst_set, conta_set, nome_conta_set, match_mode, strip_zeros):
                        writer.writerow(row)
                        write_count += 1

                    if progress_every and (read_count % progress_every == 0):
                        print(
                            f"[progresso] lidas={read_count:,} | escritas={write_count:,}",
                            file=sys.stderr,
                        )

    return read_count, write_count


def diagnose(
    inputs: Sequence[Union[str, Path]],
    inst_set: Optional[Set[str]],
    conta_set: Optional[Set[str]],
    nome_conta_set: Optional[Set[str]],
    match_mode: str,
    strip_zeros: bool,
    encoding: str,
    scan_limit: int = 200000,
    top_n: int = 10,
) -> None:
    """
    Faz um scan parcial (ou total, se menor que scan_limit) para responder:
      - há linhas para as instituições escolhidas?
      - há linhas para as contas escolhidas?
      - há interseção (instituição + conta)?
    Também imprime os valores mais frequentes vistos (CodInst e Conta).
    """
    total = 0
    ok_inst = 0
    ok_conta = 0
    ok_both = 0

    cod_counter = Counter()
    conta_counter = Counter()

    for inp in inputs:
        inp = Path(inp)
        with open(inp, "r", encoding=encoding) as fin:
            for line in fin:
                if scan_limit and total >= scan_limit:
                    break
                line = line.strip()
                if not line:
                    continue
                total += 1
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue

                cod = _normalize_str(row.get("CodInst"))
                conta = _normalize_str(row.get("Conta"))
                if strip_zeros:
                    cod = _strip_zeros_if_digits(cod)
                    conta = _strip_zeros_if_digits(conta)

                if cod:
                    cod_counter[cod] += 1
                if conta:
                    conta_counter[conta] += 1

                inst_here = True if not inst_set else (cod in inst_set)
                conta_here = True
                if conta_set or nome_conta_set:
                    nome_coluna = _normalize_str(row.get("NomeColuna")).lower()
                    by_code = (conta in conta_set) if conta_set else False
                    by_name = (nome_coluna in nome_conta_set) if nome_conta_set else False
                    if match_mode == "all":
                        if conta_set and nome_conta_set:
                            conta_here = by_code and by_name
                        else:
                            conta_here = by_code or by_name
                    else:
                        conta_here = by_code or by_name

                if inst_here:
                    ok_inst += 1
                if conta_here and (conta_set or nome_conta_set):
                    ok_conta += 1
                if inst_here and conta_here:
                    ok_both += 1

    print("\n[diagnóstico] Motivo típico de CSV vazio: não existe nenhuma linha que satisfaça TODOS os filtros ao mesmo tempo.", file=sys.stderr)
    print(f"[diagnóstico] Linhas analisadas (amostra): {total:,}", file=sys.stderr)

    if inst_set:
        print(f"[diagnóstico] Linhas que batem instituições escolhidas: {ok_inst:,}", file=sys.stderr)
        if ok_inst == 0:
            print("  -> Provável: seus CodInst NÃO aparecem neste arquivo (ou formatação diferente, ex.: sem zeros à esquerda).", file=sys.stderr)

    if conta_set or nome_conta_set:
        print(f"[diagnóstico] Linhas que batem contas/nomes escolhidos: {ok_conta:,}", file=sys.stderr)
        if ok_conta == 0:
            print("  -> Provável: suas Contas/NomeColuna NÃO aparecem neste relatório (ou códigos diferentes).", file=sys.stderr)

    if inst_set and (conta_set or nome_conta_set):
        print(f"[diagnóstico] Linhas que batem instituição + conta simultaneamente: {ok_both:,}", file=sys.stderr)
        if ok_both == 0 and ok_inst > 0 and ok_conta > 0:
            print("  -> As instituições existem no arquivo e as contas existem no arquivo, mas NÃO ocorrem juntas.", file=sys.stderr)

    if cod_counter:
        print(f"[diagnóstico] Top {top_n} CodInst (na amostra): {cod_counter.most_common(top_n)}", file=sys.stderr)
    if conta_counter:
        print(f"[diagnóstico] Top {top_n} Conta (na amostra): {conta_counter.most_common(top_n)}", file=sys.stderr)

    print("", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Extrai contas e instituições selecionadas de arquivos IF.Data (JSONL) e gera CSV."
    )
    p.add_argument("-i", "--input", nargs="+", required=True, help="Caminho(s) para JSONL(s) de entrada.")
    p.add_argument("-o", "--output", required=True, help="Caminho do CSV de saída.")

    p.add_argument("--instituicoes", default=None, help="Lista separada por vírgula de CodInst (ex.: 00058338,00000123).")
    p.add_argument("--instituicoes-file", default=None, help="Arquivo com lista de CodInst (.txt/.csv/.xlsx).")

    p.add_argument("--contas", default=None, help="Lista separada por vírgula de códigos de Conta (ex.: 78182,12345).")
    p.add_argument("--contas-file", default=None, help="Arquivo com lista de Conta (.txt/.csv/.xlsx).")
    p.add_argument("--nomes-conta", default=None, help="Lista separada por vírgula de NomeColuna (match exato, case-insensitive).")
    p.add_argument("--nomes-conta-file", default=None, help="Arquivo com lista de NomeColuna (.txt/.csv/.xlsx).")

    p.add_argument("--match-mode", choices=["any", "all"], default="any",
                   help="Como combinar filtros de conta quando 'contas' e 'nomes-conta' forem fornecidos.")
    p.add_argument("--strip-leading-zeros", action="store_true",
                   help="Ignora zeros à esquerda em CodInst/Conta na comparação (útil se alguns arquivos vêm sem padding).")

    p.add_argument("--diagnostic", action="store_true", help="Força impressão do diagnóstico (além do processamento).")
    p.add_argument("--diagnostic-scan-limit", type=int, default=200000,
                   help="Quantas linhas no máximo escanear no diagnóstico (0 = escanear tudo).")

    p.add_argument("--encoding", default="utf-8", help="Encoding de leitura do JSONL (padrão: utf-8).")
    p.add_argument("--progress-every", type=int, default=200000, help="Mostra progresso a cada N linhas lidas (0 desativa).")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    inst_list: List[str] = []
    inst_list += _parse_csv_list(args.instituicoes)
    if args.instituicoes_file:
        inst_list += _read_list_file(args.instituicoes_file, preferred_cols=["CodInst", "codinst", "instituicao", "id"])

    conta_list: List[str] = []
    conta_list += _parse_csv_list(args.contas)
    if args.contas_file:
        conta_list += _read_list_file(args.contas_file, preferred_cols=["Conta", "conta", "codigo_conta", "cod_conta"])

    nome_list: List[str] = []
    nome_list += _parse_csv_list(args.nomes_conta)
    if args.nomes_conta_file:
        nome_list += _read_list_file(args.nomes_conta_file, preferred_cols=["NomeColuna", "nomecoluna", "nome_conta", "conta_nome"])

    inst_set = _build_match_set(inst_list, strip_zeros=args.strip_leading_zeros)
    conta_set = _build_match_set(conta_list, strip_zeros=args.strip_leading_zeros)
    nome_conta_set = set(x.strip().lower() for x in nome_list if x.strip()) or None

    if inst_set is None and conta_set is None and nome_conta_set is None:
        print("[aviso] Nenhum filtro foi informado. O CSV conterá TODAS as linhas (pode ser muito grande).", file=sys.stderr)

    read_count, write_count = extract_jsonl_to_csv(
        inputs=args.input,
        output_csv=args.output,
        inst_set=inst_set,
        conta_set=conta_set,
        nome_conta_set=nome_conta_set,
        match_mode=args.match_mode,
        strip_zeros=args.strip_leading_zeros,
        encoding=args.encoding,
        progress_every=args.progress_every,
    )

    print(f"Concluído. Linhas lidas: {read_count:,} | Linhas escritas: {write_count:,}", file=sys.stderr)

    if args.diagnostic or (write_count == 0 and (inst_set or conta_set or nome_conta_set)):
        diagnose(
            inputs=args.input,
            inst_set=inst_set,
            conta_set=conta_set,
            nome_conta_set=nome_conta_set,
            match_mode=args.match_mode,
            strip_zeros=args.strip_leading_zeros,
            encoding=args.encoding,
            scan_limit=args.diagnostic_scan_limit,
        )

    print(str(Path(args.output).resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
