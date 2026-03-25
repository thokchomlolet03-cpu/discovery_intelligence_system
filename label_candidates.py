from pipeline_utils import (
    DEFAULT_LABELED_CANDIDATE_PATH,
    DEFAULT_PREDICTED_CANDIDATE_PATH,
    DEFAULT_REVIEW_QUEUE_PATH,
    load_model_bundle,
    pseudo_label_candidates,
    write_dataframe,
)
import pandas as pd


def main():
    bundle = load_model_bundle("rf_model_v1.joblib")
    df = pd.read_csv(DEFAULT_PREDICTED_CANDIDATE_PATH)
    labeled = pseudo_label_candidates(df, thresholds=bundle.get("thresholds"), config=bundle.get("config"))
    review_queue = labeled[labeled["review_candidate"]].copy()
    write_dataframe(DEFAULT_LABELED_CANDIDATE_PATH, labeled)
    write_dataframe(DEFAULT_REVIEW_QUEUE_PATH, review_queue)

    print("Pseudo-labels saved")
    print(labeled["pseudo_label"].value_counts(dropna=False))
    if "selected_for_feedback" in labeled.columns:
        accepted = int(labeled["selected_for_feedback"].sum())
        rejected = int((~labeled["selected_for_feedback"]).sum())
        print(f"Accepted: {accepted} Rejected: {rejected}")
    print(f"Review queue: {len(review_queue)}")


if __name__ == "__main__":
    main()
