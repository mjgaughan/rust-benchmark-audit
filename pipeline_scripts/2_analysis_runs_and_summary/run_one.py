#!/usr/bin/env python3
"""Run one instance end-to-end for a given variant."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Tuple

from apply_patch import apply_patch
from mutate_patch import mutate_patch_text
from policy_checks import run_policy_checks


VARIANT_TO_MODE = {
    "mut_unwrap": "unwrap",
    "unwrap": "unwrap",
    "mut_unsafe": "unsafe",
    "unsafe": "unsafe",
}


def _load_instance(instances_jsonl: Path, instance_id: str) -> Dict:
    with instances_jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("instance_id") == instance_id:
                return record
    raise ValueError(f"instance_id not found: {instance_id}")


def _repo_url(instance: Dict) -> str:
    org = instance.get("org")
    repo = instance.get("repo")
    if org and repo:
        return f"https://github.com/{org}/{repo}"
    if isinstance(repo, str) and "/" in repo:
        return f"https://github.com/{repo}"
    raise ValueError("Cannot determine repo URL from instance record")


def _run_tests(repo_dir: Path) -> Tuple[bool, str, str]:
    try:
        res = subprocess.run(
            ["cargo", "test", "-q"],
            cwd=str(repo_dir),
            text=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        return False, "", f"{exc}"
    return res.returncode == 0, res.stdout, res.stderr


def _write_log(log_path: Path, sections: Dict[str, str]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as f:
        for title, body in sections.items():
            f.write(f"=== {title} ===\n")
            if body:
                f.write(body)
                if not body.endswith("\n"):
                    f.write("\n")
            f.write("\n")


def run_instance(
    instance: Dict,
    variant: str,
    out_jsonl: Path,
    repo_base_dir: Path,
    out_dir: Path,
    cargo_target_dir: Path,
    repo_dir_override: Path | None = None,
) -> Dict:
    errors = []

    instance_id = instance.get("instance_id")
    base_commit = instance.get("base_commit")
    pr_number = instance.get("number")

    repo_url = _repo_url(instance)
    org = instance.get("org") or repo_url.rstrip("/").split("/")[-2]
    repo = instance.get("repo") or repo_url.rstrip("/").split("/")[-1]

    if repo_dir_override:
        repo_dir = repo_dir_override
    else:
        repo_dir = repo_base_dir / f"{org}__{repo}" / instance_id

    patch_dir = out_dir / "patches"
    patch_dir.mkdir(parents=True, exist_ok=True)
    patch_file = patch_dir / f"{instance_id}_{variant}.diff"

    fix_patch = instance.get("fix_patch") or ""

    mutation_count = 0
    if variant == "gold":
        patch_text = fix_patch
    else:
        mode = VARIANT_TO_MODE.get(variant)
        if not mode:
            raise ValueError(f"Unknown variant: {variant}")
        patch_text, mutation_count = mutate_patch_text(fix_patch, mode)
        if mutation_count == 0:
            errors.append("mutation_count=0")

    patch_file.write_text(patch_text, encoding="utf-8")

    cargo_target_dir = cargo_target_dir.resolve()
    cargo_target_dir.mkdir(parents=True, exist_ok=True)
    os.environ["CARGO_TARGET_DIR"] = str(cargo_target_dir)

    timings = {"checkout": 0.0, "tests": 0.0, "policy": 0.0}
    apply_ok = False
    tests_ok = False
    policy = None
    diff_stat = ""

    log_sections: Dict[str, str] = {}

    start = time.time()
    apply_ok, diff_stat, apply_logs = apply_patch(
        repo_url=repo_url,
        base_commit=base_commit,
        patch_file=patch_file,
        repo_dir=repo_dir,
    )
    timings["checkout"] = time.time() - start
    log_sections["APPLY PATCH"] = apply_logs

    if not apply_ok:
        errors.append("apply_patch_failed")
    else:
        start = time.time()
        tests_ok, tests_out, tests_err = _run_tests(repo_dir)
        timings["tests"] = time.time() - start
        log_sections["TESTS"] = tests_out + tests_err

        start = time.time()
        policy, policy_logs = run_policy_checks(repo_dir)
        timings["policy"] = time.time() - start
        log_sections["POLICY CHECKS"] = (
            policy_logs.get("fmt_stdout", "")
            + policy_logs.get("fmt_stderr", "")
            + policy_logs.get("clippy_stdout", "")
            + policy_logs.get("clippy_stderr", "")
        )

    log_path = out_dir / "logs" / f"{instance_id}_{variant}.txt"
    _write_log(log_path, log_sections)

    result = {
        "benchmark": "Multi-SWE-bench",
        "language": "Rust",
        "repo": f"{org}/{repo}",
        "instance_id": instance_id,
        "variant": variant,
        "base_commit": base_commit,
        "pr_number": pr_number,
        "tests_ok": tests_ok,
        "policy": policy,
        "apply_ok": apply_ok,
        "timing_sec": timings,
        "errors": errors,
        "artifacts": {
            "log_path": str(log_path),
            "diff_stat": diff_stat,
            "patch_path": str(patch_file),
            "mutation_count": mutation_count,
            "cargo_target_dir": str(cargo_target_dir),
        },
    }

    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with out_jsonl.open("a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=True) + "\n")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--instances-jsonl", default="data/instances.jsonl", type=Path)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--out-jsonl", default="out/results.jsonl", type=Path)
    parser.add_argument("--out-dir", default="out", type=Path)
    parser.add_argument("--repo-base-dir", default="work/repos", type=Path)
    parser.add_argument("--cargo-target-dir", default="work/cargo-target", type=Path)
    parser.add_argument("--repo-dir", default=None, type=Path)
    args = parser.parse_args()

    instance = _load_instance(args.instances_jsonl, args.instance_id)
    run_instance(
        instance=instance,
        variant=args.variant,
        out_jsonl=args.out_jsonl,
        repo_base_dir=args.repo_base_dir,
        out_dir=args.out_dir,
        cargo_target_dir=args.cargo_target_dir,
        repo_dir_override=args.repo_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
