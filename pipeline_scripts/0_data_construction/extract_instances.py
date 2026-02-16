#!/usr/bin/env python3
"""Extract selected Multi-SWE-bench instances for nushell."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def _extract_base_commit(d: dict) -> str | None:
    direct = d.get("base_commit") or d.get("commit") or d.get("repo_commit")
    if direct:
        return direct
    base = d.get("base")
    if isinstance(base, dict):
        sha = base.get("sha") or base.get("commit")
        if sha:
            return sha
    return None


def _load_instance_ids(rows_csv: Path) -> set[str]:
    with rows_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "instance_id" not in reader.fieldnames:
            raise ValueError("CSV missing required column: instance_id")
        ids = set()
        for row in reader:
            instance_id = (row.get("instance_id") or "").strip()
            if instance_id:
                ids.add(instance_id)
        return ids


def _iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield lineno, json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {lineno}: {exc}") from exc


def _normalize_record(d: dict) -> dict:
    # org/repo
    org = d.get("org")
    repo = d.get("repo")
    if org is None and isinstance(repo, str) and "/" in repo:
        org, repo = repo.split("/", 1)

    # PR number
    number = d.get("number", d.get("pr_number"))

    base_commit = _extract_base_commit(d)
    if not base_commit:
        raise KeyError(
            "Missing base_commit (checked keys: base_commit, commit, repo_commit, base.sha)"
        )

    fix_patch = d.get("fix_patch")
    if not fix_patch:
        raise KeyError("Missing fix_patch")

    title = d.get("title") or ""
    problem = d.get("problem_statement") or d.get("body") or ""

    return {
        "instance_id": d.get("instance_id"),
        "org": org,
        "repo": repo,
        "number": number,
        "base_commit": base_commit,
        "fix_patch": fix_patch,
        "title": title,
        "problem": problem,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rows-csv",
        default="data/multi_swe_bench_nushell_rows.csv",
        type=Path,
        help="CSV with instance_id column",
    )
    parser.add_argument(
        "--dataset-jsonl",
        default="data/nushell__nushell_dataset.jsonl",
        type=Path,
        help="Multi-SWE-bench JSONL file",
    )
    parser.add_argument(
        "--out-jsonl",
        default="data/instances.jsonl",
        type=Path,
        help="Output JSONL with normalized fields",
    )
    args = parser.parse_args()

    instance_ids = _load_instance_ids(args.rows_csv)
    if not instance_ids:
        print("No instance_ids found in rows CSV", file=sys.stderr)
        return 2

    out_records = []
    seen_ids = set()
    missing_base_commit_keys: set[str] = set()

    for lineno, record in _iter_jsonl(args.dataset_jsonl):
        instance_id = record.get("instance_id")
        if instance_id not in instance_ids:
            continue
        try:
            normalized = _normalize_record(record)
        except KeyError as exc:
            missing_base_commit_keys.update(record.keys())
            print(
                f"Error normalizing record at line {lineno} ({instance_id}): {exc}",
                file=sys.stderr,
            )
            return 1
        out_records.append(normalized)
        seen_ids.add(instance_id)

    missing = sorted(instance_ids - seen_ids)
    if missing:
        print(
            f"Warning: {len(missing)} instance_ids not found in dataset JSONL",
            file=sys.stderr,
        )
        for mid in missing:
            print(f"  - {mid}", file=sys.stderr)

    if missing_base_commit_keys:
        print(
            "Dataset record keys seen (for base_commit mapping):",
            ", ".join(sorted(missing_base_commit_keys)),
            file=sys.stderr,
        )

    args.out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.out_jsonl.open("w", encoding="utf-8") as f:
        for rec in out_records:
            f.write(json.dumps(rec, ensure_ascii=True) + "\n")

    print(f"Wrote {len(out_records)} records to {args.out_jsonl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
