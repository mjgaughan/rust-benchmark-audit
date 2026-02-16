
import pandas as pd
from swebench.harness.run_evaluation import run_evaluation

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
        predictions_path = f"predictions/{benchmark}_{instance_id}.json"
        save.json(predictions, predictions_path)
    return {benchmark: predictions_path}


def evaluate_predictions(predictions_paths):
    results = {}
    for benchmark in predictions_paths.keys():
        print(f"Evaluating benchmark: {benchmark}")
        benchmark_results = run_evaluation(
            predictions_path=predictions_paths[benchmark],
            dataset_name=benchmark,
            max_workers=4,
            run_id=f"{benchmark}_evaluation"
        )
        results[benchmark] = benchmark_results
    save.json(results, "swebench_results.json")
    return results

