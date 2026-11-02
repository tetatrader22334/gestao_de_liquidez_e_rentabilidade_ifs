#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
consolidar_statements_brapi.py

Consolida arquivos JSON de demonstrações financeiras no padrão BRAPI/Yahoo e gera
um statement consolidado por período.

Uso básico:
    python 12_2_consolidar_statements_brapi.py --inputs brapi/statements_BMEB4.json brapi/statements_BMIN4.json --out-dir outputs/consolid_bmin --base-name statement_consolidado --excel 

Saídas:
    *_individual_long.csv       Base normalizada: ticker/data/demonstrativo/conta/valor
    *_individual_wide.csv       Base individual em formato largo
    *_consolidated_long.csv     Statement consolidado em formato longo
    *_consolidated_wide.csv     Statement consolidado em formato largo
    *_diagnostico.csv           Cobertura por ticker/data/demonstrativo
    *_statements.xlsx           Workbook opcional, se openpyxl estiver instalado

Notas:
    - O script usa apenas a biblioteca padrão do Python para CSV/JSON.
    - Por padrão, só são somadas contas monetárias/contábeis.
    - Indicadores por ação, percentuais, margens, preços e ratios não são somados.
    - Eliminações intragrupo não são inferidas; podem ser aplicadas por CSV via --adjustments.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


STATEMENT_KEYS = {
    "balanceSheetHistoryQuarterly": "balance_sheet",
    "incomeStatementHistoryQuarterly": "income_statement",
    "valueAddedHistoryQuarterly": "value_added",
    "cashflowHistoryQuarterly": "cashflow",
}

META_IN_STATEMENT = {"symbol", "type", "endDate", "updatedAt"}

NON_ADDITIVE_EXACT = {
    "basicEarningsPerCommonShare",
    "dilutedEarningsPerCommonShare",
    "basicEarningsPerPreferredShare",
    "dilutedEarningsPerPreferredShare",
    "earningsPerShare",
    "basicEarningsPerShare",
    "dilutedEarningsPerShare",
    "priceEarnings",
    "marketCap",
}

NON_ADDITIVE_PATTERNS = [
    r"perShare", r"PerShare", r"ratio", r"Ratio", r"margin", r"Margin",
    r"percent", r"Percent", r"percentage", r"Percentage", r"yield", r"Yield",
    r"multiple", r"Multiple", r"price", r"Price",
]

INDIVIDUAL_LONG_COLS = [
    "source_file", "company_symbol", "long_name", "short_name", "currency",
    "statement", "endDate", "year", "quarter", "year_quarter", "year_month",
    "field", "value", "is_non_additive", "type", "updatedAt"
]

CONSOLIDATED_LONG_COLS = [
    "statement", "endDate", "year", "quarter", "year_quarter", "year_month",
    "field", "value", "aggregation", "is_non_additive", "entities_with_value", "tickers",
    "adjustment_value", "value_before_adjustments", "has_adjustment"
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Consolida JSONs de statements BRAPI em bases individual e consolidada."
    )
    p.add_argument("--inputs", nargs="+", required=True,
                   help="Arquivos, diretórios ou globs. Ex.: './dados/statements_*.json'")
    p.add_argument("--out-dir", default="outputs", help="Diretório de saída.")
    p.add_argument("--base-name", default="statement_consolidado", help="Prefixo das saídas.")
    p.add_argument("--statements", nargs="+", default=["all"],
                   choices=list(STATEMENT_KEYS.values()) + ["all"],
                   help="Demonstrativos: balance_sheet income_statement value_added cashflow all.")
    p.add_argument("--keep-non-additive", action="store_true",
                   help="Mantém campos não somáveis no consolidado usando média simples.")
    p.add_argument("--adjustments", default=None,
                   help="CSV opcional: endDate,statement,field,adjustment_value,note.")
    p.add_argument("--excel", action="store_true", help="Gera workbook XLSX se openpyxl estiver instalado.")
    p.add_argument("--json", action="store_true", help="Gera JSONs consolidados.")
    return p.parse_args()


def expand_inputs(inputs: Sequence[str]) -> List[Path]:
    files: List[Path] = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            files.extend(sorted(p.glob("*.json")))
        else:
            matches = sorted(glob.glob(item))
            if matches:
                files.extend(Path(m) for m in matches if Path(m).is_file())
            elif p.is_file():
                files.append(p)
    unique: List[Path] = []
    seen = set()
    for f in files:
        r = f.resolve()
        if r not in seen:
            unique.append(f)
            seen.add(r)
    if not unique:
        raise FileNotFoundError("Nenhum JSON encontrado. Verifique --inputs.")
    return unique


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except UnicodeDecodeError:
        with path.open("r", encoding="utf-8-sig") as fh:
            return json.load(fh)


def iter_results(data: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        for x in data["results"]:
            if isinstance(x, dict):
                yield x
    elif isinstance(data, list):
        for x in data:
            if isinstance(x, dict):
                yield x
    elif isinstance(data, dict):
        yield data
    else:
        raise ValueError("Estrutura JSON não reconhecida.")


def parse_end_date(value: Any) -> Optional[Dict[str, str]]:
    if not value:
        return None
    s = str(value)[:10]
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        return None
    q = ((dt.month - 1) // 3) + 1
    return {
        "endDate": dt.strftime("%Y-%m-%d"),
        "year": str(dt.year),
        "quarter": str(q),
        "year_quarter": f"{dt.year}Q{q}",
        "year_month": dt.strftime("%Y%m"),
    }


def as_number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return float(value)
    if isinstance(value, str):
        x = value.strip()
        if not x:
            return None
        # Trata formatos simples como "1.234,56" e "1234.56".
        if re.fullmatch(r"-?\d{1,3}(\.\d{3})+,\d+", x):
            x = x.replace(".", "").replace(",", ".")
        else:
            x = x.replace(",", ".")
        try:
            return float(x)
        except ValueError:
            return None
    return None


def is_non_additive(field: str) -> bool:
    if field in NON_ADDITIVE_EXACT:
        return True
    return any(re.search(p, field) for p in NON_ADDITIVE_PATTERNS)


def normalize_result(result: Dict[str, Any], source_file: Path, selected: Set[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    symbol = result.get("symbol")
    long_name = result.get("longName")
    short_name = result.get("shortName")
    currency = result.get("currency")

    for json_key, statement in STATEMENT_KEYS.items():
        if statement not in selected:
            continue
        records = result.get(json_key, [])
        if not isinstance(records, list):
            continue
        for rec in records:
            if not isinstance(rec, dict):
                continue
            date_info = parse_end_date(rec.get("endDate"))
            if not date_info:
                continue
            company_symbol = rec.get("symbol") or symbol
            for field, raw_value in rec.items():
                if field in META_IN_STATEMENT:
                    continue
                value = as_number(raw_value)
                if value is None:
                    continue
                row = {
                    "source_file": source_file.name,
                    "company_symbol": company_symbol or "",
                    "long_name": long_name or "",
                    "short_name": short_name or "",
                    "currency": currency or "",
                    "statement": statement,
                    "field": field,
                    "value": value,
                    "is_non_additive": str(is_non_additive(field)),
                    "type": rec.get("type") or "",
                    "updatedAt": rec.get("updatedAt") or "",
                }
                row.update(date_info)
                rows.append(row)
    return rows


def aggregate_individual(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    key_cols = [c for c in INDIVIDUAL_LONG_COLS if c != "value"]
    grouped: Dict[Tuple[Any, ...], float] = defaultdict(float)
    for row in rows:
        key = tuple(row.get(c, "") for c in key_cols)
        grouped[key] += float(row["value"])
    out: List[Dict[str, Any]] = []
    for key, value in grouped.items():
        row = dict(zip(key_cols, key))
        row["value"] = value
        out.append(row)
    return sorted(out, key=lambda r: (r["company_symbol"], r["endDate"], r["statement"], r["field"]))


def build_individual_long(files: Sequence[Path], selected: Set[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for f in files:
        data = load_json(f)
        for result in iter_results(data):
            rows.extend(normalize_result(result, f, selected))
    if not rows:
        raise ValueError("Nenhuma demonstração financeira encontrada nos arquivos.")
    return aggregate_individual(rows)


def consolidate_long(individual: List[Dict[str, Any]], keep_non_additive: bool) -> List[Dict[str, Any]]:
    group_cols = ["statement", "endDate", "year", "quarter", "year_quarter", "year_month", "field"]
    sums: Dict[Tuple[Any, ...], float] = defaultdict(float)
    tickers: Dict[Tuple[Any, ...], Set[str]] = defaultdict(set)
    counts: Dict[Tuple[Any, ...], int] = defaultdict(int)

    # Parte somável: soma contábil.
    for row in individual:
        non_add = row.get("is_non_additive") == "True"
        if non_add:
            continue
        key = tuple(row.get(c, "") for c in group_cols)
        sums[key] += float(row["value"])
        tickers[key].add(row.get("company_symbol", ""))
        counts[key] += 1

    out: List[Dict[str, Any]] = []
    for key, value in sums.items():
        row = dict(zip(group_cols, key))
        row.update({
            "value": value,
            "aggregation": "sum",
            "is_non_additive": "False",
            "entities_with_value": str(len(tickers[key])),
            "tickers": ",".join(sorted(tickers[key])),
            "adjustment_value": "",
            "value_before_adjustments": "",
            "has_adjustment": "False",
        })
        out.append(row)

    # Parte não somável: média simples, apenas se solicitado.
    if keep_non_additive:
        nsums: Dict[Tuple[Any, ...], float] = defaultdict(float)
        ntickers: Dict[Tuple[Any, ...], Set[str]] = defaultdict(set)
        ncounts: Dict[Tuple[Any, ...], int] = defaultdict(int)
        for row in individual:
            if row.get("is_non_additive") != "True":
                continue
            key = tuple(row.get(c, "") for c in group_cols)
            nsums[key] += float(row["value"])
            ntickers[key].add(row.get("company_symbol", ""))
            ncounts[key] += 1
        for key, value in nsums.items():
            row = dict(zip(group_cols, key))
            row.update({
                "value": value / ncounts[key] if ncounts[key] else "",
                "aggregation": "mean_non_additive",
                "is_non_additive": "True",
                "entities_with_value": str(len(ntickers[key])),
                "tickers": ",".join(sorted(ntickers[key])),
                "adjustment_value": "",
                "value_before_adjustments": "",
                "has_adjustment": "False",
            })
            out.append(row)

    return sorted(out, key=lambda r: (r["endDate"], r["statement"], r["field"]))


def apply_adjustments(consolidated: List[Dict[str, Any]], adjustments_path: Optional[str]) -> List[Dict[str, Any]]:
    if not adjustments_path:
        return consolidated
    path = Path(adjustments_path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de ajustes não encontrado: {path}")

    index: Dict[Tuple[str, str, str], Dict[str, Any]] = {
        (r["endDate"], r["statement"], r["field"]): r for r in consolidated
    }

    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        required = {"endDate", "statement", "field", "adjustment_value"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError(f"CSV de ajustes deve conter colunas: {sorted(required)}")
        for adj in reader:
            amount = as_number(adj.get("adjustment_value"))
            if amount is None:
                continue
            end_date = adj["endDate"]
            statement = adj["statement"]
            field = adj["field"]
            key = (end_date, statement, field)
            if key not in index:
                date_info = parse_end_date(end_date)
                if not date_info:
                    continue
                row = {
                    "statement": statement,
                    "field": field,
                    "value": 0.0,
                    "aggregation": "sum",
                    "is_non_additive": "False",
                    "entities_with_value": "0",
                    "tickers": "",
                    "adjustment_value": 0.0,
                    "value_before_adjustments": 0.0,
                    "has_adjustment": "False",
                }
                row.update(date_info)
                consolidated.append(row)
                index[key] = row
            row = index[key]
            before = float(row.get("value", 0) or 0)
            previous_adj = float(row.get("adjustment_value", 0) or 0)
            row["value_before_adjustments"] = before if row.get("has_adjustment") != "True" else row["value_before_adjustments"]
            row["adjustment_value"] = previous_adj + amount
            row["value"] = before + amount
            row["has_adjustment"] = "True"
    return sorted(consolidated, key=lambda r: (r["endDate"], r["statement"], r["field"]))


def make_wide(rows: List[Dict[str, Any]], index_cols: Sequence[str]) -> List[Dict[str, Any]]:
    wide: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    for row in rows:
        key = tuple(row.get(c, "") for c in index_cols)
        if key not in wide:
            wide[key] = {c: row.get(c, "") for c in index_cols}
        col = f"{row.get('statement', '')}__{row.get('field', '')}"
        wide[key][col] = row.get("value", "")
    return sorted(wide.values(), key=lambda r: tuple(r.get(c, "") for c in index_cols))


def diagnostics(individual: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
    fields: Dict[Tuple[str, str, str, str], Set[str]] = defaultdict(set)
    non_add_fields: Dict[Tuple[str, str, str, str], Set[str]] = defaultdict(set)
    for r in individual:
        key = (r["source_file"], r["company_symbol"], r["statement"], r["endDate"])
        if key not in groups:
            groups[key] = {
                "source_file": r["source_file"],
                "company_symbol": r["company_symbol"],
                "statement": r["statement"],
                "endDate": r["endDate"],
                "n_values": 0,
            }
        groups[key]["n_values"] += 1
        fields[key].add(r["field"])
        if r["is_non_additive"] == "True":
            non_add_fields[key].add(r["field"])
    out = []
    for key, row in groups.items():
        row = dict(row)
        row["n_fields"] = len(fields[key])
        row["n_non_additive_fields"] = len(non_add_fields[key])
        out.append(row)
    return sorted(out, key=lambda r: (r["company_symbol"], r["endDate"], r["statement"]))


def collect_columns(rows: List[Dict[str, Any]], preferred: Sequence[str]) -> List[str]:
    cols = list(preferred)
    seen = set(cols)
    for row in rows:
        for c in row.keys():
            if c not in seen:
                cols.append(c)
                seen.add(c)
    return cols


def write_csv(path: Path, rows: List[Dict[str, Any]], preferred_cols: Sequence[str]) -> None:
    cols = collect_columns(rows, preferred_cols)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, rows: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2)


def write_excel(path: Path, sheets: Dict[str, List[Dict[str, Any]]], preferred: Dict[str, Sequence[str]]) -> bool:
    try:
        from openpyxl import Workbook
    except ImportError:
        print("[AVISO] openpyxl não está instalado; XLSX não será gerado.")
        return False

    wb = Workbook()
    # Remove aba inicial.
    wb.remove(wb.active)
    for sheet_name, rows in sheets.items():
        ws = wb.create_sheet(sheet_name[:31])
        cols = collect_columns(rows, preferred.get(sheet_name, []))
        ws.append(cols)
        for row in rows:
            ws.append([row.get(c, "") for c in cols])
        ws.freeze_panes = "A2"
    wb.save(path)
    return True


def save_outputs(ind_long: List[Dict[str, Any]], ind_wide: List[Dict[str, Any]],
                 cons_long: List[Dict[str, Any]], cons_wide: List[Dict[str, Any]],
                 diag: List[Dict[str, Any]], out_dir: Path, base_name: str,
                 do_excel: bool, do_json: bool) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "individual_long": out_dir / f"{base_name}_individual_long.csv",
        "individual_wide": out_dir / f"{base_name}_individual_wide.csv",
        "consolidated_long": out_dir / f"{base_name}_consolidated_long.csv",
        "consolidated_wide": out_dir / f"{base_name}_consolidated_wide.csv",
        "diagnostico": out_dir / f"{base_name}_diagnostico.csv",
    }
    write_csv(paths["individual_long"], ind_long, INDIVIDUAL_LONG_COLS)
    write_csv(paths["individual_wide"], ind_wide, [])
    write_csv(paths["consolidated_long"], cons_long, CONSOLIDATED_LONG_COLS)
    write_csv(paths["consolidated_wide"], cons_wide, [])
    write_csv(paths["diagnostico"], diag, ["source_file", "company_symbol", "statement", "endDate", "n_fields", "n_values", "n_non_additive_fields"])

    if do_json:
        write_json(out_dir / f"{base_name}_consolidated_long.json", cons_long)
        write_json(out_dir / f"{base_name}_consolidated_wide.json", cons_wide)

    if do_excel:
        write_excel(
            out_dir / f"{base_name}_statements.xlsx",
            {
                "individual_long": ind_long,
                "individual_wide": ind_wide,
                "consolidated_long": cons_long,
                "consolidated_wide": cons_wide,
                "diagnostico": diag,
            },
            {
                "individual_long": INDIVIDUAL_LONG_COLS,
                "consolidated_long": CONSOLIDATED_LONG_COLS,
            },
        )

    print("\nArquivos gerados:")
    for name, p in paths.items():
        print(f" - {name}: {p}")
    if do_json:
        print(f" - json: {out_dir / f'{base_name}_consolidated_long.json'}")
        print(f" - json: {out_dir / f'{base_name}_consolidated_wide.json'}")
    if do_excel:
        print(f" - excel: {out_dir / f'{base_name}_statements.xlsx'}")


def main() -> int:
    args = parse_args()
    selected = set(STATEMENT_KEYS.values()) if "all" in args.statements else set(args.statements)
    files = expand_inputs(args.inputs)

    print(f"Arquivos encontrados: {len(files)}")
    for f in files:
        print(f" - {f}")

    ind_long = build_individual_long(files, selected)
    cons_long = consolidate_long(ind_long, args.keep_non_additive)
    cons_long = apply_adjustments(cons_long, args.adjustments)

    ind_wide = make_wide(ind_long, [
        "source_file", "company_symbol", "long_name", "short_name", "currency",
        "endDate", "year", "quarter", "year_quarter", "year_month"
    ])
    cons_wide = make_wide(cons_long, ["endDate", "year", "quarter", "year_quarter", "year_month"])
    diag = diagnostics(ind_long)

    save_outputs(ind_long, ind_wide, cons_long, cons_wide, diag,
                 Path(args.out_dir), args.base_name, args.excel, args.json)

    tickers = sorted({r["company_symbol"] for r in ind_long})
    periods = sorted({r["endDate"] for r in ind_long})
    statements = sorted({r["statement"] for r in ind_long})
    n_non_add = sum(1 for r in ind_long if r["is_non_additive"] == "True")

    print("\nResumo:")
    print(f" - Tickers: {len(tickers)} ({', '.join(tickers)})")
    print(f" - Períodos: {len(periods)}")
    print(f" - Demonstrativos: {', '.join(statements)}")
    print(f" - Linhas individuais long: {len(ind_long):,}")
    print(f" - Linhas consolidadas long: {len(cons_long):,}")
    if n_non_add and not args.keep_non_additive:
        print(f" - Campos não somáveis excluídos do consolidado: {n_non_add:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
