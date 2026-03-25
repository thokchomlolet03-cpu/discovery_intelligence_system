from pipeline_utils import clean_labels, featurize_dataframe, load_dataset


def main():
    df = load_dataset("data.csv", featurize=False)
    before = len(df)
    cleaned = clean_labels(df)
    cleaned = featurize_dataframe(cleaned)
    cleaned.to_csv("data.csv", index=False)

    print("Cleaned dataset")
    print(f"Rows kept: {len(cleaned)} / {before}")
    print(cleaned["biodegradable"].value_counts(dropna=False))


if __name__ == "__main__":
    main()
