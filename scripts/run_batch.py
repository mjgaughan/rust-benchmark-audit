#!/usr/bin/env python3
"""Run a batch of instances and emit JSONL + summary CSV."""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List


def _load_instances(instances_jsonl: Path) -> List[str]:
    ids = []
    with instances_jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            instance_id = record.get("instance_id")
            if instance_id:
                ids.append(instance_id)
    return ids


def _write_results_csv(results_jsonl: Path, out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with results_jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            policy = record.get("policy") or {}
            rows.append(
                {
                    "instance_id": record.get("instance_id"),
                    "variant": record.get("variant"),
                    "tests_ok": record.get("tests_ok"),
                    "fmt_ok": policy.get("fmt_ok"),
                    "clippy_ok": policy.get("clippy_ok"),
                    "unsafe_count": policy.get("unsafe_count"),
                    "unwrap_count": policy.get("unwrap_count"),
                    "notes": "; ".join(policy.get("notes", []) or []),
                }
            )

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "instance_id",
                "variant",
                "tests_ok",
                "fmt_ok",
                "clippy_ok",
                "unsafe_count",
                "unwrap_count",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instances-jsonl", default="data/instances.jsonl", type=Path)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--variants",
        default="gold,mut_unwrap,mut_unsafe",
        help="Comma-separated list of variants",
    )
    parser.add_argument("--out-jsonl", default="out/results.jsonl", type=Path)
    parser.add_argument("--out-csv", default="out/results.csv", type=Path)
    parser.add_argument("--out-dir", default="out", type=Path)
    parser.add_argument("--repo-base-dir", default="work/repos", type=Path)
    parser.add_argument("--cargo-target-dir", default="work/cargo-target", type=Path)
    parser.add_argument("--append", action="store_true")
    args = parser.parse_args()

    instance_ids = _load_instances(args.instances_jsonl)
    if args.limit:
        instance_ids = instance_ids[: args.limit]

    variants = [v.strip() for v in args.variants.split(",") if v.strip()]

    if not args.append and args.out_jsonl.exists():
        args.out_jsonl.unlink()
    if not args.append:
        for subdir in ("logs", "patches"):
            path = args.out_dir / subdir
            if path.exists():
                shutil.rmtree(path)

    for instance_id in instance_ids:
        for variant in variants:
            print(f"Running {instance_id} [{variant}]", flush=True)
            cmd = [
                sys.executable,
                "scripts/run_one.py",
                "--instance-id",
                instance_id,
                "--instances-jsonl",
                str(args.instances_jsonl),
                "--variant",
                variant,
                "--out-jsonl",
                str(args.out_jsonl),
                "--out-dir",
                str(args.out_dir),
                "--repo-base-dir",
                str(args.repo_base_dir),
                "--cargo-target-dir",
                str(args.cargo_target_dir),
            ]
            res = subprocess.run(cmd, text=True, capture_output=True)
            if res.returncode != 0:
                print(
                    (
                        f"run_one failed for {instance_id} ({variant}):\n"
                        f"{res.stdout}\n{res.stderr}"
                    ),
                    file=sys.stderr,
                )

    if args.out_jsonl.exists():
        _write_results_csv(args.out_jsonl, args.out_csv)
        print(f"Wrote {args.out_csv}")
    else:
        print("No results.jsonl found; CSV not written", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
