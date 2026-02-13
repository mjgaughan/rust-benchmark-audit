# benchmark-policy-gap
(This readme is vibe coded along with some of the files)
## Purpose
This repository evaluates a policy gap in code-generation benchmark evaluation for Rust tasks.

The concrete question in this implementation is:
- Can code pass benchmark tests while violating project-defined safety/style expectations?

This is implemented for a focused slice:
- Benchmark: `Multi-SWE-bench`
- Language: `Rust`
- Project: `nushell/nushell`
- Instances: 14 (`data/multi_swe_bench_nushell_rows.csv`)

## What Is Implemented
For each instance, the pipeline runs three variants:
- `gold`: original benchmark `fix_patch`
- `mut_unwrap`: policy-violating mutation that introduces `unwrap/expect` patterns where possible
- `mut_unsafe`: policy-violating mutation that introduces `unsafe` wrappers where possible

For each variant, the pipeline records:
- Patch apply success
- Test outcome (`cargo test -q`)
- Policy-check outcome (`fmt`, `clippy`, `unwrap/expect` count, `unsafe` count)
- Logs and patch artifacts

## Current Run Snapshot
The latest local run produced:
- `14` instances
- `42` records (`14 x 3 variants`)
- `out/summary_totals.csv` as aggregate view

Current aggregate totals from `out/summary_totals.csv`:

| scope | variant | total_instances | total_records | apply_ok_count | tests_ok_count | fmt_ok_count | clippy_ok_count | unwrap_total | unsafe_total |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| overall | all | 14 | 42 | 42 | 5 | 30 | 0 | 180 | 170 |
| variant | gold | 14 | 14 | 14 | 3 | 13 | 0 | 1 | 0 |
| variant | mut_unwrap | 14 | 14 | 14 | 0 | 9 | 0 | 178 | 0 |
| variant | mut_unsafe | 14 | 14 | 14 | 2 | 8 | 0 | 1 | 170 |

Additional mutation stats:
- `mut_unwrap` mutation applied in 11/14 instances, zero-change in 3/14
- `mut_unsafe` mutation applied in 11/14 instances, zero-change in 3/14

## Project Layout
```text
benchmark-policy-gap/
  data/
    nushell__nushell_dataset.jsonl
    multi_swe_bench_nushell_rows.csv
    instances.jsonl
  out/
    results.jsonl
    results.csv
    summary_by_instance.csv
    summary_totals.csv
    logs/
    patches/
  work/
    repos/
    cargo-target/
  scripts/
```

## Pipeline Details
1. `extract_instances.py`
- Reads target `instance_id` values from the CSV slice.
- Extracts matching rows from benchmark JSONL.
- Normalizes schema fields into `data/instances.jsonl` (`base_commit` is resolved from known key variants, including `base.sha`).

2. `run_one.py`
- Loads one normalized instance.
- Materializes variant patch (`gold` or mutated).
- Calls `apply_patch.py`, runs tests, runs policy checks.
- Writes one JSON record to `out/results.jsonl`.

3. `apply_patch.py`
- Clones repo if needed into `work/repos/...`.
- Resets and cleans working tree.
- Checks out detached `base_commit`.
- Applies unified diff patch.

4. `policy_checks.py`
- Runs `cargo fmt --all -- --check`.
- Runs `cargo clippy --all-targets --all-features -- -D warnings`.
- Parses `git diff --unified=0` to count `unwrap/expect` and `unsafe` in added non-test/bench Rust lines.

5. `mutate_patch.py`
- `mut_unwrap`: line-local replacement of `?`/call patterns to `unwrap()`.
- `mut_unsafe`: wraps selected statements/let assignments in `unsafe { ... }`.
- Keeps unified diff structure valid and newline-safe.

6. `run_batch.py`
- Iterates all instances and variants.
- Produces `out/results.jsonl` and `out/results.csv`.

7. Summarizers
- `summarize_results.py` -> `out/summary_by_instance.csv`
- `summarize_totals.py` -> `out/summary_totals.csv`

## NL Policy To Executable Checks
The policy text in `nushell` docs is operationalized into machine-checkable proxies:
- `fmt` policy proxy: `cargo fmt --check`
- lint/quality policy proxy: `cargo clippy -D warnings`
- explicit risky-pattern proxy: count `.unwrap()` and `.expect(` in added lines
- explicit `unsafe` proxy: count `unsafe` in added lines

This is an operationalization, not full semantic parsing of prose policy.

## Reproducibility
Environment:
- Python 3.10+
- git
- cargo

Run end-to-end:
```bash
python scripts/extract_instances.py \
  --rows-csv data/multi_swe_bench_nushell_rows.csv \
  --dataset-jsonl data/nushell__nushell_dataset.jsonl \
  --out-jsonl data/instances.jsonl

python -u scripts/run_batch.py --variants gold,mut_unwrap,mut_unsafe

python scripts/summarize_results.py \
  --results-jsonl out/results.jsonl \
  --out-csv out/summary_by_instance.csv

python scripts/summarize_totals.py \
  --results-jsonl out/results.jsonl \
  --out-csv out/summary_totals.csv
```

## Export/Handoff Guide
Minimum files to share with a collaborator:
- `README.md`
- `out/summary_totals.csv`
- `out/summary_by_instance.csv`
- `out/results.csv`
- `out/results.jsonl`

Optional (for traceability/debugging):
- `out/logs/`
- `out/patches/`

Create one archive:
```bash
tar -czf benchmark-policy-gap-export.tgz \
  README.md \
  out/summary_totals.csv \
  out/summary_by_instance.csv \
  out/results.csv \
  out/results.jsonl \
  out/logs \
  out/patches
```

## Limitations
- Test execution currently uses local `cargo test`, not the official Multi-SWE-bench docker harness.
- Policy checks are proxies and heuristics, not complete formalization of all prose policy constraints.
- `clippy_ok_count` is 0 across variants in this environment; this should be interpreted as strict `-D warnings` pressure, not necessarily mutation-specific regressions.

## Next Improvements
- Integrate official Multi-SWE-bench harness for benchmark-authentic pass/fail.
- Add mutation fallback to force non-zero mutation count for every instance.
- Extend policy encodings beyond `unwrap/expect` and `unsafe` to additional project-specific constraints.
