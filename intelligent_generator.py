from pipeline_utils import (
    DEFAULT_CANDIDATE_PATH,
    DEFAULT_GENERATED_CANDIDATE_PATH,
    DEFAULT_PROCESSED_CANDIDATE_PATH,
    generate_candidate_pool,
    load_dataset,
    process_candidate_dataframe,
    write_dataframe,
)
from system_config import default_system_config


def main():
    config = default_system_config(seed=7)
    df = load_dataset("data.csv")
    raw_pool = generate_candidate_pool(
        df,
        n=config.loop.candidates_per_round * config.generator.candidate_pool_multiplier,
        seed=config.loop.seed,
        max_attempt_multiplier=config.generator.max_attempt_multiplier,
        prefer_balanced_sources=True,
        config=config,
    )
    generated, processed = process_candidate_dataframe(raw_pool, df, config=config)
    write_dataframe(DEFAULT_GENERATED_CANDIDATE_PATH, generated)
    write_dataframe(DEFAULT_CANDIDATE_PATH, processed)
    write_dataframe(DEFAULT_PROCESSED_CANDIDATE_PATH, processed)

    print("Balanced-source candidates saved")
    print(generated.head())
    print(f"Processed candidates: {len(processed)}")


if __name__ == "__main__":
    main()
