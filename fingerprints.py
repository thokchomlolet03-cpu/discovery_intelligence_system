from pipeline_utils import FINGERPRINT_COLUMNS, featurize_dataframe, load_dataset


def main():
    df = load_dataset("data.csv", featurize=False)
    featurized = featurize_dataframe(df)
    featurized.to_csv("data.csv", index=False)

    print("Fingerprints refreshed")
    print(f"Fingerprint columns: {len(FINGERPRINT_COLUMNS)}")


if __name__ == "__main__":
    main()
