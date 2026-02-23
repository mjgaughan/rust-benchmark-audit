## TODO
- [x] Integrate SWE-bench evaluation harness for benchmark-authentic correctness checks (Matt)
- [x] Unify filtered data sets with at least benchmark/instanceID/patch_diff/augmentation/tests/etc. 
- [x] Refactor analysis pipeline following repo restructuring
- [x] Add mutation fallback to force non-zero mutation count for every instance.
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
    0_data_construction/
      scripts for the construction of input data sets
    1_patch_mutate_and_eval/
      scripts for mutating code patches and evaluating their correctness
    2_analysis_runs_and_summary/
      batching pipeline for evaluating different metrics of benchmark instances
  results/
    output statistics from analysis pipeline
```

## Pipeline Details
1. `data/sample_unification_script.py`
- Merges manually sampled rows from the benchmark subsets into `data/20260218_unified_sample.csv`.

2. `pipeline_scripts/0_data_construction/build_instances_from_unified_csv.py`
- Normalizes the unified CSV into `data/instances_unified.jsonl`.
- Resolves `base_commit` from either `base_commit` or `base.sha` in `base`.
- Resolves patch text from either `fix_patch` or `patch`.

3. `pipeline_scripts/2_analysis_runs_and_summary/run_one.py`
- Loads one normalized instance.
- Materializes variant patch (`gold` or mutated).
- Calls `apply_patch.py`, runs tests, runs policy checks.
- Writes one JSON record to `results/instance_results/results.jsonl`.

4. `pipeline_scripts/1_patch_mutate_and_eval/apply_patch.py`
- Clones repo if needed into `work/repos/...`.
- Resets and cleans working tree.
- Checks out detached `base_commit`.
- Applies unified diff patch.

5. `pipeline_scripts/0_data_construction/policy_checks.py`
- Runs `cargo fmt --all -- --check`.
- Runs `cargo clippy --all-targets --all-features -- -D warnings`.
- Parses `git diff --unified=0` to count `unwrap/expect` and `unsafe` in added non-test/bench Rust lines.

6. `pipeline_scripts/1_patch_mutate_and_eval/mutate_patch.py`
- `mut_unwrap`: line-local replacement of `?`/call patterns to `unwrap()`.
- `mut_unsafe`: wraps selected statements/let assignments in `unsafe { ... }`.
- Keeps unified diff structure valid and newline-safe.
- Includes fallback mutation logic so `mutation_count` is non-zero for mutants whenever a Rust added line is available.

7. `pipeline_scripts/2_analysis_runs_and_summary/run_batch.py`
- Iterates all instances and variants.
- Produces `results/instance_results/results.jsonl` and `results/instance_results/results.csv`.

8. Summarizers
- `pipeline_scripts/2_analysis_runs_and_summary/summarize_results.py` -> `results/instance_results/summary_by_instance.csv`
- `pipeline_scripts/2_analysis_runs_and_summary/summarize_totals.py` -> `results/summary_totals.csv`

## Latest Status (2026-02-23)
Implemented in this repo:
- Refactor fixes so the pipeline runs correctly from the current `pipeline_scripts/` tree.
- Mutation fallback to avoid zero-mutation mutant rows.
- Unified-sample normalization script for mixed benchmark schemas.
- Full unified-sample batch run completed and summarized.

Latest run artifacts:
- `data/instances_unified.jsonl` (27 normalized instances)
- `results/instance_results/results.jsonl` (81 variant records)
- `results/instance_results/summary_by_instance.csv`
- `results/summary_by_instance.csv` (copy of the same file for convenience)
- `results/summary_totals.csv`
- `results/rq_baseline_overall.csv`
- `results/rq_baseline_by_benchmark.csv`

Baseline findings from the latest unified-sample run:
- RQ1b (gold patch policy compliance): `7/27` compliant, `20/27` violating.
- RQ2 (`mut_unwrap`): `3/27` test-passing mutants, and all `3` are policy-violating.
- RQ2 (`mut_unsafe`): `8/27` test-passing mutants, and all `8` are policy-violating.

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

Run end-to-end on the unified sample:
```bash
python data/sample_unification_script.py

python pipeline_scripts/0_data_construction/build_instances_from_unified_csv.py \
  --in-csv data/20260218_unified_sample.csv \
  --out-jsonl data/instances_unified.jsonl

python -u pipeline_scripts/2_analysis_runs_and_summary/run_batch.py \
  --instances-jsonl data/instances_unified.jsonl \
  --variants gold,mut_unwrap,mut_unsafe \
  --out-jsonl results/instance_results/results.jsonl \
  --out-csv results/instance_results/results.csv \
  --out-dir results/instance_results \
  --repo-base-dir work/repos \
  --cargo-target-dir work/cargo-target

python pipeline_scripts/2_analysis_runs_and_summary/summarize_results.py \
  --results-jsonl results/instance_results/results.jsonl \
  --out-csv results/instance_results/summary_by_instance.csv

python pipeline_scripts/2_analysis_runs_and_summary/summarize_totals.py \
  --results-jsonl results/instance_results/results.jsonl \
  --out-csv results/summary_totals.csv
```

## Limitations
- Test execution currently uses local `cargo test`, not the official Multi-SWE-bench docker harness.
- Policy checks are proxies and heuristics, not complete formalization of all prose policy constraints.
- `aptos-labs/aptos-core` cloning failed in this environment because `git-lfs` is missing; this affects 3 variant rows.
- `summary_by_instance.csv` currently keys by `instance_id` only, so duplicated IDs across benchmarks can collapse to one row. Use `results/rq_baseline_*.csv` for the full 27-instance baseline summary.
