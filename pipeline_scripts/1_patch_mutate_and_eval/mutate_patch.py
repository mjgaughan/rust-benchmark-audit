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


def _mutate_panic_line(line: str, line_idx: int = -1, all_lines: list[str] | None = None) -> Tuple[str, bool]:
    """Introduce panic! calls into added code lines to simulate panic violations.
    
    Attempts to replace control flow statements or function calls with panic!.
    Mutates break/continue unconditionally, but only mutates return if it's not
    the last statement in the diff section.
    
    Matches patterns:
    - Control flow: `break;` -> `panic!("mutation");`
    - Control flow: `continue;` -> `panic!("mutation");`
    - Control flow: `return;` -> `panic!("mutation");` (only if not last line)
    
    Args:
        line: A single diff line (may start with '+' for added lines)
        line_idx: Index of the line in all_lines (optional, for context)
        all_lines: Full list of diff lines (optional, for context)
    
    Returns:
        Tuple of (potentially mutated line, boolean indicating if mutation occurred)
    """
    if not line.startswith("+") or line.startswith("+++"):
        return line, False

    newline = "\n" if line.endswith("\n") else ""
    body = line[1:-1] if newline else line[1:]

    # Skip lines that already have panic! to prevent double-mutation
    if "panic!" in body:
        return line, False

    # Pattern 1: Replace break/continue with panic! (unconditionally)
    stripped = body.strip()
    if stripped in ("break;", "continue;"):
        leading_ws = body[: len(body) - len(body.lstrip())]
        new_body = f'{leading_ws}panic!("mutation");'
        return "+" + new_body + newline, True

    # Check for return statement - only mutate if not the last added line
    if stripped.startswith("return"):
        if all_lines and line_idx >= 0:
            # Check if there are more added lines after this one
            has_more_added_lines = False
            for future_line in all_lines[line_idx + 1:]:
                if future_line.startswith("+") and not future_line.startswith("+++"):
                    has_more_added_lines = True
                    break
            
            # Only mutate return if there are more added lines after it
            if has_more_added_lines:
                leading_ws = body[: len(body) - len(body.lstrip())]
                new_body = f'{leading_ws}panic!("mutation");'
                return "+" + new_body + newline, True
        return line, False

    return line, False

def _mutate_unwrap_line(line: str) -> Tuple[str, bool]:
    """Introduce unwrap() calls into added code lines to simulate unwrap violations.
    
    Attempts to replace error handling operators with unwrap() calls.
    Matches two patterns:
    - Try operator: `expr?` -> `expr?.unwrap()`
    - Function calls: `func();` -> `func().unwrap();`
    
    Args:
        line: A single diff line (may start with '+' for added lines)
    
    Returns:
        Tuple of (potentially mutated line, boolean indicating if mutation occurred)
    """
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
    """Inject unsafe blocks into added code lines to simulate unsafe violations.
    
    Attempts to wrap function calls in unsafe blocks without corresponding //SAFETY comments.
    Matches two patterns:
    - Let assignments: `let x = func();` -> `let x = unsafe { func() };`
    - Standalone calls: `func();` -> `unsafe { func(); }`
    
    Args:
        line: A single diff line (may start with '+' for added lines)
    
    Returns:
        Tuple of (potentially mutated line, boolean indicating if mutation occurred)
    """
    if not line.startswith("+") or line.startswith("+++"):
        return line, False

    newline = "\n" if line.endswith("\n") else ""
    body = line[1:-1] if newline else line[1:]
    
    # Skip lines that already have unsafe to prevent double-mutation
    if "unsafe" in body:
        return line, False

    # Pattern 1: Let assignments with function calls
    match = LET_ASSIGN_RE.match(body)
    if match and "(" in match.group(2):
        prefix, expr, suffix = match.group(1), match.group(2), match.group(3)
        new_body = f"{prefix}unsafe {{ {expr} }};{suffix}"
        return "+" + new_body + newline, True

    # Skip declarations and other lines that can't be wrapped
    stripped = body.lstrip()
    if stripped.startswith(("use ", "fn ", "pub ", "struct ", "enum ", "impl ")):
        return line, False

    # Pattern 2: Standalone function call statements
    if CALL_LINE_RE.search(body):
        leading_ws = body[: len(body) - len(body.lstrip())]
        stmt = body.strip().rstrip(";")
        new_body = f"{leading_ws}unsafe {{ {stmt} }};"
        return "+" + new_body + newline, True

    return line, False


def _fallback_comment_mutation(lines: list[str], mode: str) -> bool:
    current_file = None
    if mode == "unwrap":
        marker = ".expect("
        comment = " // mutation_fallback .expect("
    elif mode == "unsafe":
        marker = "unsafe"
        comment = " // mutation_fallback unsafe"
    elif mode == "panic":
        marker = "panic!"
        comment = " // mutation_fallback panic!"
    else:
        return False

    for idx, line in enumerate(lines):
        if line.startswith("+++ b/"):
            current_file = line[len("+++ b/") :].strip()
            if current_file == "/dev/null":
                current_file = None
            continue

        if not line.startswith("+") or line.startswith("+++"):
            continue
        if not current_file or not current_file.endswith(".rs"):
            continue

        newline = "\n" if line.endswith("\n") else ""
        body = line[1:-1] if newline else line[1:]
        stripped = body.strip()
        if not stripped:
            continue
        if stripped.startswith("//"):
            continue
        if marker in body:
            continue

        lines[idx] = "+" + body + comment + newline
        return True

    return False


def mutate_patch_text(patch_text: str, mode: str) -> Tuple[str, int]:
    """Apply semantic mutations to a unified diff patch.
    
    Mutates added lines in the patch to violate safety policies without breaking compilation.
    Supports three mutation modes:
    - "unwrap": Replace error handling (?) with .unwrap() calls
    - "unsafe": Wrap function calls in unsafe blocks
    - "panic": Replace control flow or function calls with panic!() invocations
    
    Uses fallback comment-based mutation if no structural mutations found.
    
    Args:
        patch_text: A unified diff format patch string
        mode: One of "unwrap", "unsafe", or "panic"
    
    Returns:
        Tuple of (mutated patch text, count of mutations applied)
    """
    lines = patch_text.splitlines(keepends=True)
    mutated = []
    count = 0

    for i, line in enumerate(lines):
        if mode == "unwrap":
            new_line, changed = _mutate_unwrap_line(line)
        elif mode == "unsafe":
            new_line, changed = _mutate_unsafe_line(line)
        elif mode == "panic!":
            new_line, changed = _mutate_panic_line(line, i, lines)
        else:
            raise ValueError(f"Unknown mode: {mode}")
        mutated.append(new_line)
        if changed:
            count += 1

    if count == 0 and _fallback_comment_mutation(mutated, mode):
        count = 1

    return "".join(mutated), count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in-patch", required=True, type=Path)
    parser.add_argument("--mode", required=True, choices=["unwrap", "unsafe", "panic"])
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
