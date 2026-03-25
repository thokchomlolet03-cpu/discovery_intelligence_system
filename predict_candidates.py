from pathlib import Path

from pipeline_utils import (
    DEFAULT_CANDIDATE_PATH,
    DEFAULT_PREDICTED_CANDIDATE_PATH,
    DEFAULT_PROCESSED_CANDIDATE_PATH,
    load_dataset,
    load_model_bundle,
    predict_with_model,
    select_acquisition_portfolio,
    selection_counts,
    write_dataframe,
)


def main():
    bundle = load_model_bundle("rf_model_v1.joblib")
    config = bundle.get("config")
    candidate_path = DEFAULT_PROCESSED_CANDIDATE_PATH if Path(DEFAULT_PROCESSED_CANDIDATE_PATH).exists() else DEFAULT_CANDIDATE_PATH
    candidates = load_dataset(candidate_path)
    predicted = predict_with_model(bundle, candidates, config=config)
    predicted = select_acquisition_portfolio(predicted, config=config)
    predicted = predicted.sort_values(
        ["accepted_for_feedback", "final_score", "uncertainty"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    write_dataframe(
        DEFAULT_PREDICTED_CANDIDATE_PATH,
        predicted.sort_values(
            ["accepted_for_feedback", "final_score", "uncertainty"],
            ascending=[False, False, False],
        ).reset_index(drop=True),
    )

    ranked = predicted.sort_values(
        ["final_score", "uncertainty"],
        ascending=[False, False],
    ).reset_index(drop=True)

    print("Predictions saved")
    print(
        ranked[
            [
                "polymer",
                "confidence",
                "uncertainty",
                "novelty",
                "final_score",
                "selection_bucket",
                "accepted_for_feedback",
            ]
        ].head()
    )
    print("Confidence distribution:")
    print(ranked["confidence"].describe().round(4))
    print("Uncertainty distribution:")
    print(ranked["uncertainty"].describe().round(4))
    print("Selection counts:")
    print(selection_counts(predicted))


if __name__ == "__main__":
    main()
