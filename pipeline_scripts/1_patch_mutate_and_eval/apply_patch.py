#!/usr/bin/env python3
"""Clone a repo, checkout a base commit, and apply a unified diff patch."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Tuple


def _run(
    cmd: list[str],
    cwd: Path | None = None,
    capture: bool = False,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=capture,
    )


def _git(args: list[str], repo_dir: Path, capture: bool = False) -> subprocess.CompletedProcess:
    return _run(["git", "-C", str(repo_dir), *args], capture=capture)


def _ensure_repo(repo_url: str, repo_dir: Path) -> Tuple[bool, str]:
    logs = []
    if not repo_dir.exists():
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        res = _run(["git", "clone", repo_url, str(repo_dir)], capture=True)
        logs.append(res.stdout)
        logs.append(res.stderr)
        if res.returncode != 0:
            return False, "".join(logs)
    elif not (repo_dir / ".git").exists():
        return False, f"Repo dir exists but is not a git repo: {repo_dir}\n"

    fetch = _git(["fetch", "--all", "--tags"], repo_dir, capture=True)
    logs.append(fetch.stdout)
    logs.append(fetch.stderr)
    if fetch.returncode != 0:
        logs.append("Warning: git fetch failed; proceeding with local clone state.\n")

    return True, "".join(logs)


def apply_patch(
    repo_url: str,
    base_commit: str,
    patch_file: Path,
    repo_dir: Path,
    diff_stat_out: Path | None = None,
) -> Tuple[bool, str, str]:
    patch_file = patch_file.resolve()
    ok, logs = _ensure_repo(repo_url, repo_dir)
    if not ok:
        return False, "", logs

    # Always reset/clean before checkout so one repo clone can be reused across variants.
    reset = _git(["reset", "--hard"], repo_dir, capture=True)
    logs += reset.stdout + reset.stderr
    if reset.returncode != 0:
        return False, "", logs

    clean = _git(["clean", "-fd"], repo_dir, capture=True)
    logs += clean.stdout + clean.stderr
    if clean.returncode != 0:
        return False, "", logs

    checkout = _git(["checkout", "--detach", base_commit], repo_dir, capture=True)
    logs += checkout.stdout + checkout.stderr
    if checkout.returncode != 0:
        return False, "", logs

    apply = _git(["apply", "--whitespace=nowarn", str(patch_file)], repo_dir, capture=True)
    logs += apply.stdout + apply.stderr
    if apply.returncode != 0:
        return False, "", logs

    diff = _git(["diff", "--stat"], repo_dir, capture=True)
    diff_stat = diff.stdout.strip()
    logs += diff.stdout + diff.stderr

    if diff_stat_out:
        diff_stat_out.parent.mkdir(parents=True, exist_ok=True)
        diff_stat_out.write_text(diff_stat + "\n", encoding="utf-8")

    return True, diff_stat, logs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-url", required=True)
    parser.add_argument("--base-commit", required=True)
    parser.add_argument("--patch-file", required=True, type=Path)
    parser.add_argument(
        "--repo-dir",
        default=None,
        type=Path,
        help="Where to clone/checkout the repo",
    )
    parser.add_argument("--diff-stat-out", type=Path, default=None)
    args = parser.parse_args()

    if args.repo_dir is None:
        # Derive a default repo dir from repo-url
        repo_name = args.repo_url.rstrip("/").split("/")[-1]
        args.repo_dir = Path("work") / "repos" / repo_name

    ok, diff_stat, logs = apply_patch(
        repo_url=args.repo_url,
        base_commit=args.base_commit,
        patch_file=args.patch_file,
        repo_dir=args.repo_dir,
        diff_stat_out=args.diff_stat_out,
    )

    if logs:
        print(logs)

    if not ok:
        return 1

    if diff_stat:
        print(diff_stat)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
