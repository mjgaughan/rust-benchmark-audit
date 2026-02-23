#!/usr/bin/env python3
"""Normalize unified benchmark CSV rows into run_one/run_batch instance JSONL schema."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

import pandas as pd


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _coalesce(*values: Any) -> Any:
    for value in values:
        if not _is_missing(value):
            return value
    return None


def _extract_base_commit(value: Any) -> str | None:
    if _is_missing(value):
        return None

    if isinstance(value, dict):
        return value.get("sha") or value.get("commit")

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed.get("sha") or parsed.get("commit")
        except json.JSONDecodeError:
            pass
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, dict):
                return parsed.get("sha") or parsed.get("commit")
        except (ValueError, SyntaxError):
            pass

    return None


def _normalize_number(number_value: Any, instance_id: str) -> int | None:
    if not _is_missing(number_value):
        try:
            return int(float(number_value))
        except (TypeError, ValueError):
            pass

    if "-" in instance_id:
        suffix = instance_id.rsplit("-", 1)[-1]
        if suffix.isdigit():
            return int(suffix)
    return None


def _normalize_row(row: pd.Series) -> dict[str, Any] | None:
    instance_id = str(row.get("instance_id") or "").strip()
    if not instance_id:
        return None

    org = _coalesce(row.get("org"))
    repo = _coalesce(row.get("repo"))
    if _is_missing(repo):
        return None

    base_commit = _coalesce(row.get("base_commit"), _extract_base_commit(row.get("base")))
    fix_patch = _coalesce(row.get("fix_patch"), row.get("patch"))
    if _is_missing(base_commit) or _is_missing(fix_patch):
        return None

    number = _normalize_number(row.get("number"), instance_id)
    title = _coalesce(row.get("title"), "")
    problem = _coalesce(row.get("problem_statement"), row.get("body"), "")

    return {
        "instance_id": instance_id,
        "org": None if _is_missing(org) else str(org),
        "repo": str(repo),
        "number": number,
        "base_commit": str(base_commit),
        "fix_patch": str(fix_patch),
        "title": str(title),
        "problem": str(problem),
        "source_benchmark": str(_coalesce(row.get("source_benchmark"), row.get("benchmark"), "")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in-csv", default="data/20260218_unified_sample.csv", type=Path)
    parser.add_argument("--out-jsonl", default="data/instances_unified.jsonl", type=Path)
    args = parser.parse_args()

    df = pd.read_csv(args.in_csv)
    out_rows: list[dict[str, Any]] = []
    skipped: list[str] = []

    for _, row in df.iterrows():
        normalized = _normalize_row(row)
        if normalized is None:
            skipped.append(str(row.get("instance_id")))
            continue
        out_rows.append(normalized)

    args.out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.out_jsonl.open("w", encoding="utf-8") as f:
        for rec in out_rows:
            f.write(json.dumps(rec, ensure_ascii=True) + "\n")

    print(f"Wrote {len(out_rows)} normalized rows to {args.out_jsonl}")
    if skipped:
        print(f"Skipped {len(skipped)} rows missing required fields")
        for instance_id in skipped:
            print(f"  - {instance_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
