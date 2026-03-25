from pathlib import Path

from pipeline_utils import (
    DEFAULT_CANDIDATE_PATH,
    DEFAULT_GENERATED_CANDIDATE_PATH,
    DEFAULT_PROCESSED_CANDIDATE_PATH,
    load_dataset,
    process_candidate_dataframe,
    write_dataframe,
)
from system_config import default_system_config


def main():
    config = default_system_config()
    source_path = DEFAULT_GENERATED_CANDIDATE_PATH if Path(DEFAULT_GENERATED_CANDIDATE_PATH).exists() else DEFAULT_CANDIDATE_PATH
    df = load_dataset(source_path, featurize=False)
    reference = load_dataset("data.csv", featurize=False)
    scored, processed = process_candidate_dataframe(df, reference, config=config)
    write_dataframe(DEFAULT_CANDIDATE_PATH, processed)
    write_dataframe(DEFAULT_PROCESSED_CANDIDATE_PATH, processed)

    print("Candidates processed")
    print(f"Rows: {len(processed)}")
    rejected = int(len(scored) - len(processed))
    print(f"Accepted: {len(processed)} Rejected: {rejected}")
    if not scored.empty:
        print(scored[["polymer", "novelty", "max_similarity", "batch_max_similarity", "rejection_reason"]].head())


if __name__ == "__main__":
    main()
