import pandas as pd
from swebench.harness import run_evaluation
import json
import sys
import subprocess
from pathlib import Path
import shutil
from datetime import datetime
import os
from collections import defaultdict

def create_predictions_from_mutated_instances(mutated_instances):
    '''
    Convert mutated instances to swebench predictions format, grouped by source_benchmark.
    
    Each mutated_instance should have:
    - instance_id
    - diff (the patch content)
    - mutation (mutation type: 'gs', 'unsafe', 'unwrap', 'panic!')
    - source_benchmark (benchmark name for grouping)
    
    output prediction format for each instance:
    {
    "instance_id": "repo_owner__repo_name-issue_number",
    "model_name_or_path": "your-model-name",
    "model_patch": "the patch content as a string"
    }
    
    Returns:
        dict: mapping of benchmark -> predictions_path
    '''
    
    # Group instances by source_benchmark
    instances_by_benchmark = defaultdict(list)
    for instance in mutated_instances:
        benchmark = instance.get('hf_bm')
        if not benchmark:
            raise ValueError(f"Instance {instance.get('instance_id')} missing source_benchmark field")
        instances_by_benchmark[benchmark].append(instance)
    
    # Create predictions files for each benchmark
    predictions_paths = {}
    for benchmark, instances in instances_by_benchmark.items():
        predictions = []
        for instance in instances:
            prediction = {
                "instance_id": instance['instance_id'],
                "model_name_or_path": instance['mutation'],  # mutation type (gs, unsafe, unwrap, panic!)
                "model_patch": instance['diff']  # the patch content
            }
            predictions.append(prediction)
        
        # Save to temp file
        benchmark_path = benchmark.replace('/', '_')
        predictions_path = f"{benchmark_path}_mutated_temp.json"
        with open(predictions_path, 'w') as f:
            json.dump(predictions, f, indent=2)
        predictions_paths[benchmark] = predictions_path
    
    return predictions_paths


def create_predictions_from_dataframe(df, benchmark):
    '''
    output prediction format
    {
    "instance_id": "repo_owner__repo_name-issue_number",
    "model_name_or_path": "your-model-name",
    "model_patch": "the patch content as a string"
    }
    '''
    predictions = []
    for _, row in df.iterrows():
        instance_id = f"{row['instance_id']}"
        model_name_or_path = row['augmentation']
        model_patch = row['patch_diff']
        
        prediction = {
            "instance_id": instance_id,
            "model_name_or_path": model_name_or_path,
            "model_patch": model_patch
        }
        predictions.append(prediction)
    benchmark_path = benchmark.replace('/', '_')
    predictions_path = f"{benchmark_path}_temp.json"
    with open(predictions_path, 'w') as f:
        json.dump(predictions, f, indent=2)
    return predictions_path


def evaluate_predictions(predictions_paths):
    results = {}
    for benchmark in predictions_paths.keys():
        print(f"Evaluating benchmark: {benchmark}")
        #update the run_id to reflect the benchmark and date/time of evaluation
        run_id = f"{benchmark.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"Running evaluation with run_id: {run_id}")
        cmd = [
            sys.executable, '-m', 'swebench.harness.run_evaluation',
            '--predictions_path', predictions_paths[benchmark],
            '--dataset_name', benchmark,
            '--max_workers', '4',
            '--run_id', run_id,
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        results[benchmark] = result.stdout
        benchmark_path = benchmark.replace('/', '_')
        with open(f"{benchmark_path}_results.json", 'w') as f:
            json.dump(results[benchmark], f, indent=2)
    
    return results

def collate_and_clean_results(run_id, predictions_paths):
    logs_dir = Path(f"logs/run_evaluation/{run_id}/gs/")

    all_results = {}
    
    for instance_dir in logs_dir.iterdir():
        if instance_dir.is_dir():
            report_path = instance_dir / "report.json"
            
            if report_path.exists():
                try:
                    with open(report_path, 'r') as f:
                        report_data = json.load(f)
                        # Add instance_id to the report data
                        report_data['instance_id'] = instance_dir.name
                        report_data['run_id'] = run_id
                        all_results[run_id+'_'+instance_dir.name] = report_data
                except json.JSONDecodeError as e:
                    print(f"Error reading {report_path}: {e}")
    
    # Save collated results_date
    output_path = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_swebench_evals_total.json"
    with open(output_path, 'w') as f:
        json.dump(all_results, f, indent=2)

    #cleaning up temporary predictions files
    for benchmark, path in predictions_paths.items():
        print(f"Removing temporary predictions file: {benchmark} - {path}")
        shutil.rmtree(Path(f"logs/run_evaluation/{run_id}/"))
        os.remove(path)

if __name__ == "__main__":
    '''
    # testing with swebench-lite gs
    df = pd.read_csv("data/benchmark-sets/test-swebench-lite.csv")
    df['benchmark'] = 'swe-bench/swe-bench_lite'
    df['patch_diff'] = df['patch']
    df['augmentation'] = 'gs'
    df = df.head(8)

    # Create predictions in the required format for evaluation
    benchmarks = df['benchmark'].unique()
    predictions_paths = {}
    for benchmark in benchmarks:
        benchmark_df = df[df['benchmark'] == benchmark]
        predictions_paths[benchmark] = create_predictions_from_dataframe(benchmark_df, benchmark)
    '''
    predictions_paths = {'TuringEnterprises/SWE-Bench-plus-plus': 'TuringEnterprises_SWE-Bench-plus-plus_mutated_temp.json'}
    # Evaluate the predictions and save results
    results_run_id = evaluate_predictions(predictions_paths)
    
    collate_and_clean_results(results_run_id, predictions_paths)
