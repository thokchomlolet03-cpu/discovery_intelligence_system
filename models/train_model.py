from system.services.artifact_service import write_evaluation_summary
from system.services.data_service import load_dataset
from system.services.training_service import save_model_bundle, train_model as train_bundle_model


def train_model(X, y, config=None, random_state=None):
    frame = X.copy()
    frame["biodegradable"] = y
    bundle = train_bundle_model(frame, random_state=random_state or 42, config=config)
    return bundle["model"], bundle["features"], bundle


def main():
    dataset = load_dataset("data.csv")
    bundle = train_bundle_model(dataset)
    save_model_bundle(bundle, "rf_model_v1.joblib")
    write_evaluation_summary("evaluation_summary.json", bundle)
    selected = bundle["selected_model"]
    print(f"Selected model: {selected['name']} ({selected['calibration_method']})")


if __name__ == "__main__":
    main()
