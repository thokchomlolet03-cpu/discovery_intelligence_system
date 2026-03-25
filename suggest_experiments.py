from pipeline_utils import load_dataset, load_model_bundle, predict_with_model


def main():
    bundle = load_model_bundle("rf_model_v1.joblib")
    df = load_dataset("data.csv")
    scored = predict_with_model(bundle, df, config=bundle.get("config"))
    ranked = scored.sort_values(["uncertainty", "novelty", "final_score"], ascending=[False, False, False])

    print("Suggested experiments")
    print(ranked[["polymer", "smiles", "biodegradable", "confidence", "uncertainty", "novelty", "final_score"]].head(10))

    ranked.to_csv("uncertainty_ranked.csv", index=False)


if __name__ == "__main__":
    main()
