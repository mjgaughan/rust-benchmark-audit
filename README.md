/data and /results are the current working directories for 20260226
- /data contains different requisite data (gs, mutations) for evaluation on the actual evaluation harnesses (which Matt has been running on the CL)
- /pipeline_scripts does still contain policy check stuff, but e2e pipeline has been paused for the moment 
- /results contains policy check results and json files from harness evaluationsß

## TODO
- [x] Integrate SWE-bench evaluation harness for benchmark-authentic correctness checks (Matt)
- [x] Unify filtered data sets with at least benchmark/instanceID/patch_diff/augmentation/tests/etc. 
- [x] Refactor analysis pipeline following repo restructuring
- [x] Add mutation fallback to force non-zero mutation count for every instance.
- [~] get pipeline to run e2e simply
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
For each instance, the pipeline runs four variants:
- `gold`: original benchmark `fix_patch`
- `mut_unwrap`: policy-violating mutation that introduces `unwrap/expect` patterns where possible
- `mut_unsafe`: policy-violating mutation that introduces `unsafe` wrappers where possible
- `mut_panic`: policy-violating mutation that introduces `panic!` patterns where possible

Mutation generation supports two styles:
- `heuristic` (default): minimal syntax-local edits.
- `adversarial`: stronger policy-violating edits (including real `unsafe` pointer activity patterns).

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
- `mut_panic`: swaps selected statements to `panic!("mutation")`.
- `--style heuristic|adversarial`: choose mutation strength profile.
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

## Latest Harness Run (2026-03-01 Linux Server)
Run command used:
```bash
python3 -u pipeline_scripts/2_analysis_runs_and_summary/bare_run_all.py \
  --instances-jsonl data/instances_unified.jsonl \
  --mutations gs,unwrap,unsafe,panic \
  --mutation-style heuristic \
  --run-eval \
  --max-workers 2 \
  --docker-host unix:///var/run/docker.sock \
  --eval-output-dir results/harness_eval_20260301_042428
```

Primary artifacts:
- `results/harness_eval_20260301_042428/evaluation_runs.csv`
- `results/harness_eval_20260301_042428/evaluation_runs.jsonl`
- `results/harness_outcomes_20260301_042428_compact.csv` (12-row compact table for slides)
- `results/harness_outcomes_latest_compact.csv` (latest-pointer copy)
- `results/harness_resolution_20260301_042428.csv` (resolved counts by benchmark+mutation)
- `results/20260301_042428_harness_summary.md`
- `results/e2e_20260301_042428.log`
- `results/mutated_instances_20260301_042428.jsonl` (`108` rows)
- `results/policy_check_results_20260301_042428.jsonl` (`108` rows)

Note:
- This run used the `heuristic` mutation style.
- For stronger pilot evidence, rerun with `--mutation-style adversarial` (recommended for unsafe/panic stress tests).

## Claude Override Harness Run (2026-03-02 Linux Server)
Run command used:
```bash
python3 -u pipeline_scripts/2_analysis_runs_and_summary/bare_run_all.py \
  --instances-jsonl data/instances_unified.jsonl \
  --mutations gs,unwrap,unsafe,panic \
  --external-predictions-commit 04f34fc \
  --require-external-predictions \
  --run-eval \
  --max-workers 2 \
  --docker-host unix:///var/run/docker.sock \
  --eval-output-dir results/harness_eval_20260302_055806
```

Primary artifacts:
- `results/harness_eval_20260302_055806/evaluation_runs.csv`
- `results/harness_eval_20260302_055806/evaluation_runs.jsonl`
- `results/harness_outcomes_20260302_055806_compact.csv`
- `results/harness_resolution_20260302_055806.csv`
- `results/20260302_055806_harness_summary.md`
- `results/e2e_20260302_055806.log`

Job-level outcomes (`12` total):
- `4` skipped: `ByteDance-Seed/Multi-SWE-bench` (`gs/panic/unsafe/unwrap`) due known dataset-loader incompatibility.
- `8` completed with `status=ok` and `returncode=0` (Multilingual + SWE-Bench++).
- `0` runner-level failures.

Resolved reports by benchmark+mutation:
- Multilingual: `gs=10/10`, `unsafe=10/10`, `unwrap=10/10`, `panic=2/10`.
- SWE-Bench++: `gs=3/3`, `unsafe=3/3`, `unwrap=3/3`, `panic=0/3`.

Important caveat:
- External Claude `panic` patches from commit `04f34fc` are partially malformed unified diffs for this harness flow.
- Evidence: patch-apply errors (`patch: **** malformed patch at line ...`) in panic stderr logs.
- Interpretation: `gs/unsafe/unwrap` from this run are usable; `panic` is incomplete and should be rerun with generated mutations.

Job-level outcomes (`12` total):
- `4` skipped: `ByteDance-Seed/Multi-SWE-bench` (`gs/panic/unsafe/unwrap`) due known dataset-loader incompatibility.
- `8` succeeded: `SWE-bench/SWE-bench_Multilingual` and `TuringEnterprises/SWE-Bench-plus-plus` (all four mutations each).
- `0` failed.

Multilingual outcomes by mutation (10 submitted each):
- `gs`: `10` resolved, `0` unresolved.
- `panic`: `10` resolved, `0` unresolved.
- `unsafe`: `10` resolved, `0` unresolved.
- `unwrap`: `7` resolved, `3` unresolved.

Unresolved multilingual instances:
- `unwrap`: `uutils__coreutils-6377`, `uutils__coreutils-6731`, `nushell__nushell-12901`

SWE-Bench++ outcomes by mutation (3 submitted each):
- `gs`: `2` resolved, `1` unresolved (`uutils__coreutils-8478`)
- `panic`: `2` resolved, `1` unresolved (`uutils__coreutils-8478`)
- `unsafe`: `2` resolved, `1` unresolved (`uutils__coreutils-8478`)
- `unwrap`: `1` resolved, `2` unresolved (`uutils__coreutils-8478`, `unicode-org__icu4x-6776`)

SWE-Bench++ runner fix status:
- The runner now normalizes malformed `PASS_TO_PASS`/`FAIL_TO_PASS` fields and infers missing `version` values from `instance_id`.
- The wrapper dynamically patches missing `swebench` repo/version specs from dataset `environment_config`.
- The wrapper also registers missing Rust log parsers for repos not present in upstream parser maps.
- The full 2026-03-01 run confirms `ok` status for all four SWE-Bench++ mutation jobs.

Policy-count totals from this run (`results/policy_check_results_20260301_042428.jsonl`):
- `gs`: `unwrap=6`, `unsafe=1`, `panic=1`, `unsafe_without_safety_comment=0`
- `unwrap`: `unwrap=33`, `unsafe=1`, `panic=1`, `unsafe_without_safety_comment=0`
- `unsafe`: `unwrap=6`, `unsafe=28`, `panic=1`, `unsafe_without_safety_comment=0`
- `panic`: `unwrap=6`, `unsafe=1`, `panic=4`, `unsafe_without_safety_comment=0`

## Presentation Scope Update (2026-03-01)
- Current presentation scope is `SWE-bench/SWE-bench_Multilingual` and `TuringEnterprises/SWE-Bench-plus-plus`.
- `ByteDance-Seed/Multi-SWE-bench` is deferred until after presentation due current dataset-loader incompatibility in upstream `swebench`/`datasets`.
- For stronger mutation evidence, use `--mutation-style adversarial` in reruns.
- Historical Claude-mutated patch snapshots are recoverable from commit `04f34fc` under `data/mutated_patches/`.

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

Run mutation generation + SWE-bench harness preparation:
```bash
python pipeline_scripts/2_analysis_runs_and_summary/bare_run_all.py \
  --instances-jsonl data/instances_unified.jsonl \
  --mutations gs,unwrap,unsafe,panic \
  --mutation-style heuristic \
  --mutated-out-jsonl results/mutated_instances.jsonl \
  --policy-out-jsonl results/policy_check_results.jsonl \
  --predictions-dir data/mutated_patches
```

Run the same flow and execute the SWE-bench harness:
```bash
python pipeline_scripts/2_analysis_runs_and_summary/bare_run_all.py \
  --instances-jsonl data/instances_unified.jsonl \
  --mutations gs,unwrap,unsafe,panic \
  --mutation-style heuristic \
  --run-eval \
  --eval-output-dir results/harness_eval
```

Adversarial rerun (stronger mutation profile):
```bash
python pipeline_scripts/2_analysis_runs_and_summary/bare_run_all.py \
  --instances-jsonl data/instances_unified.jsonl \
  --mutations gs,unwrap,unsafe,panic \
  --mutation-style adversarial \
  --run-eval \
  --max-workers 2 \
  --docker-host unix:///var/run/docker.sock \
  --eval-output-dir results/harness_eval_adversarial_$(date +%Y%m%d_%H%M%S)
```

Use historical Claude mutations directly from commit `04f34fc`:
```bash
python pipeline_scripts/2_analysis_runs_and_summary/bare_run_all.py \
  --instances-jsonl data/instances_unified.jsonl \
  --mutations gs,unwrap,unsafe,panic \
  --external-predictions-commit 04f34fc \
  --require-external-predictions \
  --run-eval \
  --max-workers 2 \
  --docker-host unix:///var/run/docker.sock \
  --eval-output-dir results/harness_eval_claude_$(date +%Y%m%d_%H%M%S)
```

External prediction overrides can also come from a local folder:
```bash
python pipeline_scripts/2_analysis_runs_and_summary/bare_run_all.py \
  --instances-jsonl data/instances_unified.jsonl \
  --mutations gs,unwrap,unsafe,panic \
  --external-predictions-dir data/mutated_patches \
  --require-external-predictions \
  --run-eval
```

Optional: force Docker host if Docker Desktop socket is not auto-detected:
```bash
python pipeline_scripts/2_analysis_runs_and_summary/bare_run_all.py \
  --run-eval \
  --docker-host unix://$HOME/.docker/run/docker.sock
```

Optional (arch override, mostly for Apple Silicon debugging):
```bash
SWEBENCH_ARCH=arm64 python pipeline_scripts/2_analysis_runs_and_summary/bare_run_all.py --run-eval
```

## Limitations
- Test execution currently uses local `cargo test`, not the official Multi-SWE-bench docker harness.
- Policy checks are proxies and heuristics, not complete formalization of all prose policy constraints.
- `aptos-labs/aptos-core` cloning failed in this environment because `git-lfs` is missing; this affects 3 variant rows.
- `summary_by_instance.csv` currently keys by `instance_id` only, so duplicated IDs across benchmarks can collapse to one row. Use `results/rq_baseline_*.csv` for the full 27-instance baseline summary.
- SWE-bench harness execution requires `swebench` (and runtime dependencies like Docker) to be installed in the active Python environment.
- By default, eval runs skip `ByteDance-Seed/Multi-SWE-bench` because of a known dataset loading incompatibility with current `swebench`/`datasets`; use `--include-known-incompatible` to force it.
- Historical note: early 2026-02-28 SWE-Bench++ harness runs failed before instance grading; use the post-fix runner in this repo for current runs.
