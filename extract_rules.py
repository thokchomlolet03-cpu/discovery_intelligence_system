from pipeline_utils import DESCRIPTOR_COLUMNS, labeled_subset, load_dataset


def main():
    df = labeled_subset(load_dataset("data.csv"))

    print("Descriptor rule summary")
    for feature in DESCRIPTOR_COLUMNS:
        threshold = df[feature].median()
        below_rate = df.loc[df[feature] < threshold, "biodegradable"].mean()
        above_rate = df.loc[df[feature] >= threshold, "biodegradable"].mean()

        print(f"\nFeature: {feature}")
        print(f"Median threshold: {threshold:.3f}")
        print(f"Below threshold biodegradable rate: {below_rate:.3f}")
        print(f"Above threshold biodegradable rate: {above_rate:.3f}")


if __name__ == "__main__":
    main()
