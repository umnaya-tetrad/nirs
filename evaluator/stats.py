"""Small statistical helpers with deterministic seeds."""
from __future__ import annotations

import math
import random


def precision_recall_f1(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def paired_bootstrap_ci(differences: list[float], *, samples: int = 10000, seed: int = 0, alpha: float = 0.05) -> dict[str, float]:
    n = len(differences)
    if n == 0:
        return {"diff": 0.0, "ci_low": 0.0, "ci_high": 0.0}
    rng = random.Random(seed)
    diff = sum(differences) / n
    stats = sorted(
        sum(differences[rng.randrange(n)] for _ in range(n)) / n
        for _ in range(samples)
    )
    low_index = max(0, int((alpha / 2) * samples) - 1)
    high_index = min(samples - 1, int((1 - alpha / 2) * samples))
    return {"diff": diff, "ci_low": stats[low_index], "ci_high": stats[high_index]}


def wilson_interval(successes: int, total: int, *, z: float = 1.959963984540054) -> dict[str, float]:
    if total == 0:
        return {"center": 0.0, "low": 0.0, "high": 0.0}
    phat = successes / total
    denom = 1 + z * z / total
    center = (phat + z * z / (2 * total)) / denom
    margin = z * math.sqrt(phat * (1 - phat) / total + z * z / (4 * total * total)) / denom
    return {"center": center, "low": max(0.0, center - margin), "high": min(1.0, center + margin)}
