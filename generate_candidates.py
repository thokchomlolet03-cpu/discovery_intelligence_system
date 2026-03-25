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
    config = default_system_config()
    df = load_dataset("data.csv")
    raw_pool = generate_candidate_pool(
        df,
        n=config.loop.candidates_per_round * config.generator.candidate_pool_multiplier,
        seed=config.loop.seed,
        max_attempt_multiplier=config.generator.max_attempt_multiplier,
        prefer_balanced_sources=config.generator.prefer_balanced_sources,
        config=config,
    )
    generated, processed = process_candidate_dataframe(raw_pool, df, config=config)

    write_dataframe(DEFAULT_GENERATED_CANDIDATE_PATH, generated)
    write_dataframe(DEFAULT_CANDIDATE_PATH, processed)
    write_dataframe(DEFAULT_PROCESSED_CANDIDATE_PATH, processed)

    print("Generated candidates")
    print(generated.head())
    print(f"Raw pool: {len(generated)}")
    print(f"Processed candidates: {len(processed)}")
    if "novelty" in generated.columns and not generated.empty:
        print("Novelty distribution:")
        print(generated["novelty"].dropna().describe().round(4))
        print("Rejection reasons:")
        print(generated["rejection_reason"].replace("", "accepted").value_counts(dropna=False))


if __name__ == "__main__":
    main()
