from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


def infer_type(values: list[str]) -> str:
    present = [value.strip() for value in values if value.strip()]
    if not present:
        return "empty"
    if all(value.casefold() in {"true", "false"} for value in present):
        return "boolean"
    if all(re.fullmatch(r"[+-]?\d+", value) for value in present):
        return "integer"
    try:
        for value in present:
            Decimal(value)
        return "number"
    except InvalidOperation:
        pass
    try:
        for value in present:
            date.fromisoformat(value)
        return "date"
    except ValueError:
        return "string"


def matches_type(value: str, expected: str) -> bool:
    value = value.strip()
    expected = expected.casefold()
    if expected == "string":
        return True
    if expected == "integer":
        return bool(re.fullmatch(r"[+-]?\d+", value))
    if expected == "number":
        try:
            Decimal(value)
            return True
        except InvalidOperation:
            return False
    if expected == "boolean":
        return value.casefold() in {"true", "false"}
    if expected == "date":
        try:
            date.fromisoformat(value)
            return True
        except ValueError:
            return False
    raise ValueError(f"Unsupported contract type: {expected}")


def load_contract(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    with path.open("r", encoding="utf-8-sig") as source:
        contract = json.load(source)
    if not isinstance(contract, dict):
        raise ValueError("Contract root must be a JSON object.")
    if not isinstance(contract.get("columns", {}), dict):
        raise ValueError("'columns' must be a JSON object.")
    if not isinstance(contract.get("unique", []), list):
        raise ValueError("'unique' must be a JSON array.")
    return contract


def validate(source: Path, contract: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    rows: list[list[str]] = []
    try:
        with source.open("r", newline="", encoding="utf-8-sig") as stream:
            reader = csv.reader(stream)
            headers = next(reader, None)
            if headers is None:
                return {"file": source.name, "valid": False, "rows": 0, "columns": [], "errors": ["CSV is empty."]}
            for line_number, row in enumerate(reader, start=2):
                if len(row) != len(headers):
                    errors.append(f"Line {line_number}: expected {len(headers)} fields, found {len(row)}.")
                rows.append(row)
    except (OSError, UnicodeError, csv.Error) as error:
        return {"file": source.name, "valid": False, "rows": 0, "columns": [], "errors": [str(error)]}

    if any(not header.strip() for header in headers):
        errors.append("Header contains an empty column name.")
    if len(set(headers)) != len(headers):
        errors.append("Header contains duplicate column names.")

    declared = contract.get("columns", {})
    missing = [name for name in declared if name not in headers]
    if missing:
        errors.append("Missing required columns: " + ", ".join(missing) + ".")

    column_reports = []
    for index, name in enumerate(headers):
        values = [row[index] for row in rows if len(row) == len(headers)]
        present = [value for value in values if value.strip()]
        rule = declared.get(name, {})
        if not isinstance(rule, dict):
            errors.append(f"Contract rule for '{name}' must be an object.")
            rule = {}
        expected = rule.get("type")
        nullable = rule.get("nullable", True)
        null_count = len(values) - len(present)
        if expected:
            try:
                for row_number, value in enumerate(values, start=2):
                    if not value.strip() and not nullable:
                        errors.append(f"Line {row_number}: '{name}' cannot be empty.")
                    elif value.strip() and not matches_type(value, expected):
                        errors.append(f"Line {row_number}: '{name}' must be {expected}; found {value!r}.")
            except ValueError as error:
                errors.append(str(error))
        elif not nullable and null_count:
            errors.append(f"'{name}' cannot be empty ({null_count} empty value(s)).")
        column_reports.append({
            "name": name,
            "inferred_type": infer_type(values),
            "rows": len(values),
            "empty_values": null_count,
            "distinct_values": len(set(present)),
        })

    for index, key in enumerate(contract.get("unique", []), start=1):
        columns = [key] if isinstance(key, str) else key
        if not isinstance(columns, list) or not columns or any(name not in headers for name in columns):
            errors.append(f"Unique rule {index} refers to an invalid column set.")
            continue
        positions = [headers.index(name) for name in columns]
        seen: set[tuple[str, ...]] = set()
        for row_number, row in enumerate(rows, start=2):
            if len(row) != len(headers):
                continue
            value = tuple(row[position].strip() for position in positions)
            if value in seen:
                errors.append(f"Line {row_number}: duplicate value for unique key ({', '.join(columns)}).")
            seen.add(value)

    min_rows = contract.get("min_rows")
    max_rows = contract.get("max_rows")
    if min_rows is not None and len(rows) < min_rows:
        errors.append(f"Expected at least {min_rows} rows; found {len(rows)}.")
    if max_rows is not None and len(rows) > max_rows:
        errors.append(f"Expected at most {max_rows} rows; found {len(rows)}.")

    return {"file": source.name, "valid": not errors, "rows": len(rows), "columns": column_reports, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(prog="tabular-contract", description="Profile a CSV and validate it against a small JSON data contract.")
    parser.add_argument("csv_file", type=Path, help="CSV file to inspect")
    parser.add_argument("--contract", type=Path, help="Optional JSON contract file")
    args = parser.parse_args()
    try:
        contract = load_contract(args.contract)
        report = validate(args.csv_file, contract)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"tabular-contract: {error}", file=sys.stderr)
        return 2
    print(f"{'PASS' if report['valid'] else 'FAIL'}  {report['file']}")
    print(f"{report['rows']} row(s) · {len(report['columns'])} column(s)")
    for column in report["columns"]:
        print(f"  {column['name']}: {column['inferred_type']}, {column['distinct_values']} distinct, {column['empty_values']} empty")
    for error in report["errors"]:
        print(f"ERROR  {error}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())