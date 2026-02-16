#!/usr/bin/env python3
"""Create aggregate totals CSV from variant-level results.jsonl."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


VARIANTS = ("gold", "mut_unwrap", "mut_unsafe")


def _b(val) -> bool:
    return bool(val)


def _policy(rec: dict, key: str):
    return (rec.get("policy") or {}).get(key)


def _to_int(val):
    if val is None:
        return 0
    return int(val)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-jsonl", default="out/results.jsonl", type=Path)
    parser.add_argument("--out-csv", default="out/summary_totals.csv", type=Path)
    args = parser.parse_args()

    rows = []
    with args.results_jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("variant") in VARIANTS:
                rows.append(rec)

    by_variant = {v: [] for v in VARIANTS}
    by_instance: dict[str, dict[str, dict]] = {}

    for rec in rows:
        variant = rec["variant"]
        instance_id = rec.get("instance_id")
        by_variant[variant].append(rec)
        by_instance.setdefault(instance_id, {})[variant] = rec

    all_instances = sorted(by_instance.keys())

    out_rows = []

    # Overall totals across all variant records.
    out_rows.append(
        {
            "scope": "overall",
            "variant": "all",
            "total_instances": len(all_instances),
            "total_records": len(rows),
            "apply_ok_count": sum(_b(r.get("apply_ok")) for r in rows),
            "tests_ok_count": sum(_b(r.get("tests_ok")) for r in rows),
            "fmt_ok_count": sum(_b(_policy(r, "fmt_ok")) for r in rows),
            "clippy_ok_count": sum(_b(_policy(r, "clippy_ok")) for r in rows),
            "unwrap_total": sum(_to_int(_policy(r, "unwrap_count")) for r in rows),
            "unsafe_total": sum(_to_int(_policy(r, "unsafe_count")) for r in rows),
            "mutation_zero_count": "",
            "mutation_nonzero_count": "",
            "gold_tests_ok_count": sum(_b((by_instance[i].get("gold") or {}).get("tests_ok")) for i in all_instances),
            "test_regression_count": "",
            "policy_violation_count": "",
        }
    )

    for variant in VARIANTS:
        recs = by_variant[variant]
        mutation_zero = ""
        mutation_nonzero = ""
        test_regression_count = ""
        policy_violation_count = ""

        if variant != "gold":
            mutation_zero = sum(_to_int((r.get("artifacts") or {}).get("mutation_count")) == 0 for r in recs)
            mutation_nonzero = sum(_to_int((r.get("artifacts") or {}).get("mutation_count")) > 0 for r in recs)

            regressions = 0
            policy_violations = 0
            for instance_id in all_instances:
                g = by_instance[instance_id].get("gold") or {}
                m = by_instance[instance_id].get(variant) or {}

                g_tests = _b(g.get("tests_ok"))
                m_tests = _b(m.get("tests_ok"))
                if g_tests and not m_tests:
                    regressions += 1

                g_unwrap = _to_int(_policy(g, "unwrap_count"))
                g_unsafe = _to_int(_policy(g, "unsafe_count"))
                m_unwrap = _to_int(_policy(m, "unwrap_count"))
                m_unsafe = _to_int(_policy(m, "unsafe_count"))
                m_fmt = _b(_policy(m, "fmt_ok"))
                m_clippy = _b(_policy(m, "clippy_ok"))

                if variant == "mut_unwrap":
                    violation = (not m_fmt) or (not m_clippy) or (m_unwrap > g_unwrap)
                else:
                    violation = (not m_fmt) or (not m_clippy) or (m_unsafe > g_unsafe)
                if violation:
                    policy_violations += 1

            test_regression_count = regressions
            policy_violation_count = policy_violations

        out_rows.append(
            {
                "scope": "variant",
                "variant": variant,
                "total_instances": len(all_instances),
                "total_records": len(recs),
                "apply_ok_count": sum(_b(r.get("apply_ok")) for r in recs),
                "tests_ok_count": sum(_b(r.get("tests_ok")) for r in recs),
                "fmt_ok_count": sum(_b(_policy(r, "fmt_ok")) for r in recs),
                "clippy_ok_count": sum(_b(_policy(r, "clippy_ok")) for r in recs),
                "unwrap_total": sum(_to_int(_policy(r, "unwrap_count")) for r in recs),
                "unsafe_total": sum(_to_int(_policy(r, "unsafe_count")) for r in recs),
                "mutation_zero_count": mutation_zero,
                "mutation_nonzero_count": mutation_nonzero,
                "gold_tests_ok_count": sum(_b((by_instance[i].get("gold") or {}).get("tests_ok")) for i in all_instances),
                "test_regression_count": test_regression_count,
                "policy_violation_count": policy_violation_count,
            }
        )

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "scope",
        "variant",
        "total_instances",
        "total_records",
        "apply_ok_count",
        "tests_ok_count",
        "fmt_ok_count",
        "clippy_ok_count",
        "unwrap_total",
        "unsafe_total",
        "mutation_zero_count",
        "mutation_nonzero_count",
        "gold_tests_ok_count",
        "test_regression_count",
        "policy_violation_count",
    ]

    with args.out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"Wrote {len(out_rows)} rows to {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
