import numpy as np


def compute_uncertainty(probs):
    arr = np.asarray(probs, dtype=float)
    return 1.0 - (np.abs(arr - 0.5) * 2.0)

