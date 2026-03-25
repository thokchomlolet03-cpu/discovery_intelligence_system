import random


def simulate_experiment(row, noise=0.1, seed=None):
    rng = random.Random(seed)
    base = float(row.get("confidence", 0.5))
    pseudo_ground_truth = min(max(base + rng.uniform(-noise, noise), 0.0), 1.0)
    return int(pseudo_ground_truth >= 0.5)

