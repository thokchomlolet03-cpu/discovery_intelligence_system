import argparse
from pathlib import Path

from pipeline_utils import (
    DEFAULT_EVALUATION_PATH,
    DEFAULT_RUN_CONFIG_PATH,
    load_dataset,
    train_model,
    write_evaluation_summary,
    write_run_config,
)
from system.services.artifact_service import register_artifact_root
from system_config import default_system_config


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate the discovery system without mutating data.csv")
    parser.add_argument("--data-path", default="data.csv", help="Input dataset CSV path")
    parser.add_argument("--output-dir", default=".", help="Directory for evaluation artifacts")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    return parser.parse_args()


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    register_artifact_root(output_dir)
    config = default_system_config(seed=args.seed)
    dataset = load_dataset(args.data_path)
    bundle = train_model(dataset, random_state=args.seed, config=config)

    write_run_config(output_dir / DEFAULT_RUN_CONFIG_PATH, config)
    write_evaluation_summary(output_dir / DEFAULT_EVALUATION_PATH, bundle)

    selected = bundle["selected_model"]
    holdout = bundle["metrics"]["holdout"]
    print("Evaluation complete")
    print(f"Selected model: {selected['name']} ({selected['calibration_method']})")
    print(f"Balanced accuracy: {holdout['balanced_accuracy']:.4f}")
    print(f"Brier score: {holdout['brier_score']:.4f}")
    print(f"Log loss: {holdout['log_loss']:.4f}")


if __name__ == "__main__":
    main()
