#!/usr/bin/env python3
"""Run project-defined safety/style checks for nushell."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

PANIC_RE = re.compile(r"\bpanic!\(")
UNWRAP_RE = re.compile(r"\.unwrap\(\)")
EXPECT_RE = re.compile(r"\.expect\(")
UNSAFE_RE = re.compile(r"\bunsafe\b")
SAFETY_COMMENT_RE = re.compile(r"//\s*SAFETY\s*:", re.IGNORECASE)


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )


def _is_test_or_bench(path: str) -> bool:
    if path.startswith("tests/") or path.startswith("benches/"):
        return True
    if "/tests/" in path or "/benches/" in path:
        return True
    return False


def count_from_bm_diff(diff_text: str) -> Tuple[int, int, int]:
    unwrap_count = 0
    unsafe_count = 0
    panic_count = 0
    unsafe_without_safety_comment = 0
    current_file = None
    diff_lines = diff_text.splitlines()

    for i, line in enumerate(diff_lines):
        if line.startswith("diff --git "):
            current_file = None
            continue
        if line.startswith("+++ b/"):
            current_file = line[len("+++ b/") :]
            if current_file == "/dev/null":
                current_file = None
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        if not current_file:
            continue
        if not current_file.endswith(".rs"):
            continue
        if _is_test_or_bench(current_file):
            continue

        added = line[1:]
        unwrap_count += len(UNWRAP_RE.findall(added))
        unwrap_count += len(EXPECT_RE.findall(added))
        panic_count += len(PANIC_RE.findall(added))
        
        # Count unsafe occurrences
        unsafe_in_line = len(UNSAFE_RE.findall(added))
        unsafe_count += unsafe_in_line
        
        # If checking for safety comments and unsafe was found, look for corresponding comment
        if unsafe_in_line > 0:
            # Check if this line or surrounding lines have a SAFETY comment
            has_safety = SAFETY_COMMENT_RE.search(added)
            if not has_safety:
                # Check preceding and following lines for SAFETY comment
                for j in range(max(0, i - 10), min(len(diff_lines), i + 4)):
                    if SAFETY_COMMENT_RE.search(diff_lines[j]):
                        has_safety = True
                        break
            
            if not has_safety:
                unsafe_without_safety_comment += unsafe_in_line

    results ={
        "unwrap_count": unwrap_count,
        "unsafe_count": unsafe_count,
        "panic_count": panic_count,
        "unsafe_without_safety_comment": unsafe_without_safety_comment,
    }
    return results


def _count_from_diff(repo_dir: Path, check_safety_comments: bool = False) -> Tuple[int, int, int, int]:
    diff = _run(["git", "diff", "--unified=0"], repo_dir)
    if diff.returncode != 0:
        return 0, 0, 0, 0

    unwrap_count = 0
    unsafe_count = 0
    panic_count = 0
    unsafe_without_safety_comment = 0
    current_file = None
    diff_lines = diff.stdout.splitlines()

    for i, line in enumerate(diff_lines):
        if line.startswith("diff --git "):
            current_file = None
            continue
        if line.startswith("+++ b/"):
            current_file = line[len("+++ b/") :]
            if current_file == "/dev/null":
                current_file = None
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        if not current_file:
            continue
        if not current_file.endswith(".rs"):
            continue
        if _is_test_or_bench(current_file):
            continue

        added = line[1:]
        unwrap_count += len(UNWRAP_RE.findall(added))
        unwrap_count += len(EXPECT_RE.findall(added))
        panic_count += len(PANIC_RE.findall(added))
        
        # Count unsafe occurrences
        unsafe_in_line = len(UNSAFE_RE.findall(added))
        unsafe_count += unsafe_in_line
        
        unsafe_without_safety_comment = 0
        # If checking for safety comments and unsafe was found, look for corresponding comment
        if check_safety_comments and unsafe_in_line > 0:
            # Check if this line or surrounding lines have a SAFETY comment
            has_safety = SAFETY_COMMENT_RE.search(added)
            if not has_safety:
                # Check preceding and following lines for SAFETY comment
                for j in range(max(0, i - 10), min(len(diff_lines), i + 4)):
                    if SAFETY_COMMENT_RE.search(diff_lines[j]):
                        has_safety = True
                        break
            
            if not has_safety:
                unsafe_without_safety_comment += unsafe_in_line

        result = {
        "unwrap_count": unwrap_count,
        "unsafe_count": unsafe_count,
        "panic_count": panic_count,
        "unsafe_without_safety_comment": unsafe_without_safety_comment,
    }
        
    return result

def run_policy_checks(repo_dir: Path) -> Tuple[Dict, Dict]:
    notes: List[str] = []

    fmt = _run(["cargo", "fmt", "--all", "--", "--check"], repo_dir)
    fmt_ok = fmt.returncode == 0
    if not fmt_ok:
        notes.append("cargo fmt failed")

    clippy = _run(
        ["cargo", "clippy", "--all-targets", "--all-features", "--", "-D", "warnings"],
        repo_dir,
    )
    clippy_ok = clippy.returncode == 0
    if not clippy_ok:
        notes.append("cargo clippy failed")

    unwrap_count, unsafe_count, panic_count, unsafe_without_safety = _count_from_diff(repo_dir, check_safety_comments=True)
    if unwrap_count > 0:
        notes.append("unwrap/expect found in added lines")
    if unsafe_count > 0:
        notes.append("unsafe found in added lines")
    if panic_count > 0:
        notes.append("panic! found in added lines")
    if unsafe_without_safety > 0:
        notes.append("unsafe without //SAFETY comment found in added lines")

    result = {
        "fmt_ok": fmt_ok,
        "clippy_ok": clippy_ok,
        "unwrap_count": unwrap_count,
        "unsafe_count": unsafe_count,
        "panic_count": panic_count,
        "unsafe_without_safety_comment": unsafe_without_safety,
        "notes": notes,
    }

    logs = {
        "fmt_stdout": fmt.stdout,
        "fmt_stderr": fmt.stderr,
        "clippy_stdout": clippy.stdout,
        "clippy_stderr": clippy.stderr,
    }

    return result, logs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-dir", required=True, type=Path)
    parser.add_argument("--out-json", required=True, type=Path)
    args = parser.parse_args()

    result, _logs = run_policy_checks(args.repo_dir)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(result, ensure_ascii=True) + "\n", encoding="utf-8")

    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
