#!/usr/bin/env python3
"""Create per-instance summary CSV from variant-level results.jsonl."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


VARIANTS = ("gold", "mut_unwrap", "mut_unsafe")


def _bool(x):
    return bool(x) if x is not None else None


def _policy_field(rec: dict, key: str):
    policy = rec.get("policy") or {}
    return policy.get(key)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-jsonl", default="out/results.jsonl", type=Path)
    parser.add_argument("--out-csv", default="out/summary_by_instance.csv", type=Path)
    args = parser.parse_args()

    rows = []
    with args.results_jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))

    per_instance: dict[str, dict] = {}
    for rec in rows:
        instance_id = rec.get("instance_id")
        variant = rec.get("variant")
        if not instance_id or variant not in VARIANTS:
            continue
        slot = per_instance.setdefault(
            instance_id,
            {
                "instance_id": instance_id,
                "repo": rec.get("repo"),
                "pr_number": rec.get("pr_number"),
                "base_commit": rec.get("base_commit"),
                "gold": None,
                "mut_unwrap": None,
                "mut_unsafe": None,
            },
        )
        slot[variant] = rec

    out_rows = []
    for instance_id in sorted(per_instance.keys()):
        row = per_instance[instance_id]
        g = row["gold"] or {}
        u = row["mut_unwrap"] or {}
        s = row["mut_unsafe"] or {}

        g_tests = _bool(g.get("tests_ok"))
        u_tests = _bool(u.get("tests_ok"))
        s_tests = _bool(s.get("tests_ok"))

        g_fmt = _bool(_policy_field(g, "fmt_ok"))
        u_fmt = _bool(_policy_field(u, "fmt_ok"))
        s_fmt = _bool(_policy_field(s, "fmt_ok"))

        g_clippy = _bool(_policy_field(g, "clippy_ok"))
        u_clippy = _bool(_policy_field(u, "clippy_ok"))
        s_clippy = _bool(_policy_field(s, "clippy_ok"))

        g_unwrap = _policy_field(g, "unwrap_count") or 0
        u_unwrap = _policy_field(u, "unwrap_count") or 0
        s_unwrap = _policy_field(s, "unwrap_count") or 0

        g_unsafe = _policy_field(g, "unsafe_count") or 0
        u_unsafe = _policy_field(u, "unsafe_count") or 0
        s_unsafe = _policy_field(s, "unsafe_count") or 0

        u_mut_count = (u.get("artifacts") or {}).get("mutation_count")
        s_mut_count = (s.get("artifacts") or {}).get("mutation_count")

        out_rows.append(
            {
                "instance_id": instance_id,
                "repo": row.get("repo"),
                "pr_number": row.get("pr_number"),
                "base_commit": row.get("base_commit"),
                "gold_tests_ok": g_tests,
                "mut_unwrap_tests_ok": u_tests,
                "mut_unsafe_tests_ok": s_tests,
                "gold_fmt_ok": g_fmt,
                "mut_unwrap_fmt_ok": u_fmt,
                "mut_unsafe_fmt_ok": s_fmt,
                "gold_clippy_ok": g_clippy,
                "mut_unwrap_clippy_ok": u_clippy,
                "mut_unsafe_clippy_ok": s_clippy,
                "gold_unwrap_count": g_unwrap,
                "mut_unwrap_unwrap_count": u_unwrap,
                "mut_unsafe_unwrap_count": s_unwrap,
                "gold_unsafe_count": g_unsafe,
                "mut_unwrap_unsafe_count": u_unsafe,
                "mut_unsafe_unsafe_count": s_unsafe,
                "mut_unwrap_mutation_count": u_mut_count,
                "mut_unsafe_mutation_count": s_mut_count,
                "test_regression_mut_unwrap": bool(g_tests) and not bool(u_tests),
                "test_regression_mut_unsafe": bool(g_tests) and not bool(s_tests),
                "policy_violation_mut_unwrap": (not bool(u_fmt)) or (not bool(u_clippy)) or u_unwrap > g_unwrap,
                "policy_violation_mut_unsafe": (not bool(s_fmt)) or (not bool(s_clippy)) or s_unsafe > g_unsafe,
            }
        )

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "instance_id",
        "repo",
        "pr_number",
        "base_commit",
        "gold_tests_ok",
        "mut_unwrap_tests_ok",
        "mut_unsafe_tests_ok",
        "gold_fmt_ok",
        "mut_unwrap_fmt_ok",
        "mut_unsafe_fmt_ok",
        "gold_clippy_ok",
        "mut_unwrap_clippy_ok",
        "mut_unsafe_clippy_ok",
        "gold_unwrap_count",
        "mut_unwrap_unwrap_count",
        "mut_unsafe_unwrap_count",
        "gold_unsafe_count",
        "mut_unwrap_unsafe_count",
        "mut_unsafe_unsafe_count",
        "mut_unwrap_mutation_count",
        "mut_unsafe_mutation_count",
        "test_regression_mut_unwrap",
        "test_regression_mut_unsafe",
        "policy_violation_mut_unwrap",
        "policy_violation_mut_unsafe",
    ]
    with args.out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"Wrote {len(out_rows)} rows to {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
