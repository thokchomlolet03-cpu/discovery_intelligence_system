import numpy as np

from pipeline_utils import DESCRIPTOR_COLUMNS, extract_feature_importances, load_model_bundle


def main():
    bundle = load_model_bundle("rf_model_v1.joblib")
    importances = extract_feature_importances(bundle)

    ranking = sorted(
        importances.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    print("Global feature importance")
    for feature, value in ranking[:20]:
        print(f"{feature}: {value:.6f}")

    descriptor_total = float(
        np.sum([importance for feature, importance in ranking if feature in DESCRIPTOR_COLUMNS])
    )
    print("\nDescriptor importance share")
    print(f"{descriptor_total:.4f}")


if __name__ == "__main__":
    main()
