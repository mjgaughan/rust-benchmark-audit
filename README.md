## TODO
- [ ] Integrate SWE-bench evaluation harness for benchmark-authentic correctness checks (Matt)
- [ ] Unify filtered data sets with at least benchmark/instanceID/patch_diff/augmentation/tests/etc. 
- [ ] Refactor analysis pipeline following repo restructuring
- [ ] Aggregate selected rows from all three benchmarks into one dataframe for analysis 
- [ ] Add mutation fallback to force non-zero mutation count for every instance.
- [ ] Extend policy encodings beyond `unwrap/expect` and `unsafe` to additional project-specific constraints.
  - [ ] Double-check the current policy encodings 
  - [ ] See if it makes sense to add in verification analysis?

  
# Rust CodeGen Auditing Pipeline
Disclaimer: Portions of the respository are vibecoded with FOO BAR.

## Purpose / Motivation
This repository evaluates a policy gap in code-generation benchmark evaluation for Rust tasks.

The concrete question in this implementation is:
- Can code pass benchmark tests while violating project-defined safety/style expectations?

This research focuses on the following benchmarks: 
- `Multi-SWE-bench`
- `SWE-bench Multilingual`
- `SWE-bench++`

## What Is Implemented
For each instance, the pipeline runs three variants:
- `gold`: original benchmark `fix_patch`
- `mut_unwrap`: policy-violating mutation that introduces `unwrap/expect` patterns where possible
- `mut_unsafe`: policy-violating mutation that introduces `unsafe` wrappers where possible

For each patch variant, the pipeline records:
- Patch apply success
- Test outcome (`cargo test -q`)
- Policy-check outcome (`fmt`, `clippy`, `unwrap/expect` count, `unsafe` count)
- Logs and patch artifacts

## Project Layout
```text
benchmark-policy-gap/
  data/
    instance and summary data frames of manually-filtered Rust rows within popular CodeGen benchmarks
  pipeline_scripts/
    0_data construction/
      scripts for the construction of input data sets
    1_patch_mutate_and_eval/
      scripts for mutating code patches and evaluating their correctness
    2_analysis_runs_and_summary/
      batching pipeline for evaluating different metrics of benchmark instances
  results/
    output statistics from analysis pipeline
```

## TODO: Pipeline Details
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

## NL Policy To Executable Checks (TODO: manual update of policy executables?)
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

## Limitations
- Test execution currently uses local `cargo test`, not the official Multi-SWE-bench docker harness.
- Policy checks are proxies and heuristics, not complete formalization of all prose policy constraints.
- `clippy_ok_count` is 0 across variants in this environment; this should be interpreted as strict `-D warnings` pressure, not necessarily mutation-specific regressions.
