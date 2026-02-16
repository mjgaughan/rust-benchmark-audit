#!/usr/bin/env python3
"""Mutate a unified diff patch to violate policy while likely compiling."""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Tuple

QUESTION_MARK_RE = re.compile(r"\?([;,\)\]\}])")
QUESTION_SEMI_RE = re.compile(r"\?[ \t]*;")
CALL_LINE_RE = re.compile(r"\w+[ \t]*\(.*\)[ \t]*;[ \t]*$")
LET_ASSIGN_RE = re.compile(r"^([ \t]*let[ \t]+[^=]+?=[ \t]*)(.+?);([ \t]*(//.*)?)$")


def _mutate_unwrap_line(line: str) -> Tuple[str, bool]:
    if not line.startswith("+") or line.startswith("+++"):
        return line, False

    newline = "\n" if line.endswith("\n") else ""
    body = line[1:-1] if newline else line[1:]
    if "?" in body:
        if QUESTION_MARK_RE.search(body):
            new_body = QUESTION_MARK_RE.sub(r".unwrap()\1", body, count=1)
            return "+" + new_body + newline, True
        if QUESTION_SEMI_RE.search(body):
            new_body = QUESTION_SEMI_RE.sub(".unwrap();", body, count=1)
            return "+" + new_body + newline, True

    if ".unwrap(" in body or ".expect(" in body:
        return line, False
    if CALL_LINE_RE.search(body):
        new_body = re.sub(r"\)[ \t]*;[ \t]*$", ").unwrap();", body, count=1)
        return "+" + new_body + newline, True

    return line, False


def _mutate_unsafe_line(line: str) -> Tuple[str, bool]:
    if not line.startswith("+") or line.startswith("+++"):
        return line, False

    newline = "\n" if line.endswith("\n") else ""
    body = line[1:-1] if newline else line[1:]
    if "unsafe" in body:
        return line, False

    match = LET_ASSIGN_RE.match(body)
    if match and "(" in match.group(2):
        prefix, expr, suffix = match.group(1), match.group(2), match.group(3)
        new_body = f"{prefix}unsafe {{ {expr} }};{suffix}"
        return "+" + new_body + newline, True

    stripped = body.lstrip()
    if stripped.startswith(("use ", "fn ", "pub ", "struct ", "enum ", "impl ")):
        return line, False

    if CALL_LINE_RE.search(body):
        leading_ws = body[: len(body) - len(body.lstrip())]
        stmt = body.strip().rstrip(";")
        new_body = f"{leading_ws}unsafe {{ {stmt} }};"
        return "+" + new_body + newline, True

    return line, False


def mutate_patch_text(patch_text: str, mode: str) -> Tuple[str, int]:
    lines = patch_text.splitlines(keepends=True)
    mutated = []
    count = 0

    for line in lines:
        if mode == "unwrap":
            new_line, changed = _mutate_unwrap_line(line)
        elif mode == "unsafe":
            new_line, changed = _mutate_unsafe_line(line)
        else:
            raise ValueError(f"Unknown mode: {mode}")
        mutated.append(new_line)
        if changed:
            count += 1

    return "".join(mutated), count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in-patch", required=True, type=Path)
    parser.add_argument("--mode", required=True, choices=["unwrap", "unsafe"])
    parser.add_argument("--out-patch", required=True, type=Path)
    args = parser.parse_args()

    patch_text = args.in_patch.read_text(encoding="utf-8")
    mutated_text, count = mutate_patch_text(patch_text, args.mode)

    if count == 0:
        print("Warning: no mutations applied", flush=True)

    args.out_patch.parent.mkdir(parents=True, exist_ok=True)
    args.out_patch.write_text(mutated_text, encoding="utf-8")
    print(f"Wrote mutated patch to {args.out_patch} (mutations: {count})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
