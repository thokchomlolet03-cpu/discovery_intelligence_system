import sys

from pipeline_utils import featurize_dataframe, load_dataset


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "data"
    file_name = "data.csv" if mode == "data" else "candidates.csv"

    raw = load_dataset(file_name, featurize=False)
    before = len(raw)
    featured = featurize_dataframe(raw)
    featured.to_csv(file_name, index=False)

    print(f"Generated descriptors and fingerprints for {file_name}")
    print(f"Valid molecules: {len(featured)} / {before}")


if __name__ == "__main__":
    main()
