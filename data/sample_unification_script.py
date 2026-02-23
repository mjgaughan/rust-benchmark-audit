import pandas as pd 
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
# load the three data sets in sampled_data
multisb_sample = pd.read_csv(DATA_DIR / "manually_sampled_data/sampled_multisb_rows.csv")
swepp_sample = pd.read_csv(DATA_DIR / "manually_sampled_data/sampled_pp_rows.csv")
sbmulti_sample = pd.read_csv(DATA_DIR / "manually_sampled_data/sampled_sbmulti_rows.csv")

# Strip whitespace from column names
multisb_sample.columns = multisb_sample.columns.str.strip()
swepp_sample.columns = swepp_sample.columns.str.strip()
sbmulti_sample.columns = sbmulti_sample.columns.str.strip()

# concatenate the three data sets into one
combined_sample = pd.concat([multisb_sample, swepp_sample, sbmulti_sample], ignore_index=True)
# get unique benchmark values
unique_benchmarks = combined_sample['benchmark'].unique()
print(f"Unique benchmarks: {unique_benchmarks}\n")

# Map benchmark names to their parquet files
benchmark_file_map = {
    "swe-bench_plus-plus": DATA_DIR / "benchmark-sets/20260218_swe-bench_plus-plus.parquet",
    "swe-bench_multilingual": DATA_DIR / "benchmark-sets/20260218_swe-bench_multilingual.parquet",
    "multi-swe-bench": DATA_DIR / "benchmark-sets/20260218_multi-swe-bench_nushell.jsonl"
}

# for each unique benchmark, look up instance_ids and pull out rows from the benchmark files
all_matching_rows = []

for benchmark in unique_benchmarks:
    # filter rows for this benchmark from combined sample
    benchmark_rows = combined_sample[combined_sample['benchmark'] == benchmark]
    instance_ids = benchmark_rows['instance_id'].unique()
    
    print(f"\nBenchmark: {benchmark}")
    print(f"Number of instances: {len(instance_ids)}")
    print(f"Instance IDs: {instance_ids}")
    
    # Load the corresponding benchmark file
    file_path = benchmark_file_map.get(benchmark)
    if file_path:
        if str(file_path).endswith('.parquet'):
            benchmark_data = pd.read_parquet(file_path)
        elif str(file_path).endswith('.jsonl'):
            benchmark_data = pd.read_json(file_path, lines=True)
        else:
            print(f"Unsupported file format for {benchmark}")
            continue
        
        # Find rows with matching instance_ids
        matching_rows = benchmark_data[benchmark_data['instance_id'].isin(instance_ids)].copy()
        # Add a column to track which benchmark this row came from
        matching_rows['source_benchmark'] = benchmark
        all_matching_rows.append(matching_rows)
        print(f"\nRows for {benchmark}:")
        print(matching_rows['instance_id'])
    else:
        print(f"No benchmark file found for {benchmark}")
    print("-" * 80)

# Combine all matching rows into one unified dataframe
if all_matching_rows:
    unified_df = pd.concat(all_matching_rows, ignore_index=True)
    
    # Define desired column order
    priority_columns = ['source_benchmark', 'instance_id', 'org', 'repo', 'patch', 'fix_patch', 'test_patch']
    # Get remaining columns (excluding priority columns)
    remaining_columns = [col for col in unified_df.columns if col not in priority_columns]
    # Reorder: priority columns first, then remaining columns
    column_order = priority_columns + remaining_columns
    # Only include columns that actually exist in the dataframe
    column_order = [col for col in column_order if col in unified_df.columns]
    unified_df = unified_df[column_order]
    
    print("\n" + "=" * 80)
    print("UNIFIED DATAFRAME:")
    print("=" * 80)
    print(f"Total rows: {len(unified_df)}")
    print(f"Columns: {list(unified_df.columns)}")
    print("\nDataframe head:")
    print(unified_df.head())
    print("\nRows per benchmark:")
    print(unified_df['source_benchmark'].value_counts())
    unified_df.to_csv(DATA_DIR / "20260218_unified_sample.csv", index=False)
else:
    print("No matching rows found!")
