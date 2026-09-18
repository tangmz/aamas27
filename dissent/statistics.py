"""Paired question-cluster inference, implemented without runtime dependencies."""

import itertools
import math
import random
from collections import defaultdict


def quantile(values, p):
    values = sorted(values)
    position = (len(values) - 1) * p
    lo, hi = math.floor(position), math.ceil(position)
    return values[lo] + (values[hi] - values[lo]) * (position - lo)


def exact_mcnemar(wins, losses):
    """Two-sided exact binomial test on discordant independent question pairs."""
    n = wins + losses
    if not n:
        return 1.0
    k = min(wins, losses)
    probabilities = [math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) - n * math.log(2)) for i in range(k + 1)]
    return min(1.0, 2 * math.fsum(probabilities))


def holm_adjust(pvalues):
    valid = sorted((p, i) for i, p in enumerate(pvalues) if p is not None)
    adjusted = [None] * len(pvalues)
    previous = 0
    for rank, (p, i) in enumerate(valid):
        previous = max(previous, min(1.0, (len(valid) - rank) * p))
        adjusted[i] = previous
    return adjusted


def paired_inference(pairs, samples=2000, seed=2027):
    """pairs contain task_id, stratum, treatment, baseline. Repetitions stay clustered.

    Estimate = mean treatment-minus-baseline over complete task/repetition pairs.
    Bootstrap resamples whole questions within source/family strata. A question's
    repetitions are always carried together. Sign-flip p-values assume cluster-level
    treatment/baseline exchangeability under the null; they are exploratory.
    """
    if samples < 1:
        raise ValueError("Positive resampling count required")
    clusters = defaultdict(list)
    strata_for = {}
    for pair in pairs:
        key = pair["task_id"]
        if key in strata_for and strata_for[key] != pair["stratum"]:
            raise ValueError("A task cannot belong to different strata")
        strata_for[key] = pair["stratum"]
        clusters[key].append(int(pair["treatment"]) - int(pair["baseline"]))
    if not pairs:
        return {"n_pairs": 0, "n_questions": 0, "difference": None, "bootstrap_95": None, "p_value": None, "test": None, "wins": 0, "losses": 0}
    difference = sum(sum(v) for v in clusters.values()) / len(pairs)
    grouped = defaultdict(list)
    for key, values in sorted(clusters.items()):
        grouped[strata_for[key]].append((sum(values), len(values)))
    rng = random.Random(seed)
    distribution = []
    if len(clusters) >= 2:
        for _ in range(samples):
            numerator = denominator = 0
            for group in grouped.values():
                for _ in group:
                    total, size = rng.choice(group)
                    numerator += total
                    denominator += size
            distribution.append(numerator / denominator)
    wins = sum(p["treatment"] > p["baseline"] for p in pairs)
    losses = sum(p["treatment"] < p["baseline"] for p in pairs)
    if all(len(v) == 1 for v in clusters.values()):
        pvalue = exact_mcnemar(wins, losses)
        test = "exact_mcnemar"
    else:
        totals = [sum(v) for v in clusters.values() if sum(v)]
        observed = abs(sum(totals))
        if len(totals) <= 12:
            signs = itertools.product((-1, 1), repeat=len(totals))
            extreme = sum(abs(sum(a * b for a, b in zip(totals, pattern))) >= observed for pattern in signs)
            pvalue = extreme / 2**len(totals)
            test = "exact_question_cluster_sign_flip"
        else:
            extreme = sum(abs(sum(total * rng.choice((-1, 1)) for total in totals)) >= observed for _ in range(samples))
            pvalue = (extreme + 1) / (samples + 1)
            test = "monte_carlo_question_cluster_sign_flip"
    return {"n_pairs": len(pairs), "n_questions": len(clusters), "difference": difference,
            "bootstrap_95": [quantile(distribution, 0.025), quantile(distribution, 0.975)] if distribution else None,
            "p_value": pvalue, "test": test, "wins": wins, "losses": losses,
            "bootstrap_samples": samples, "seed": seed,
            "bootstrap_degenerate": bool(distribution) and min(distribution) == max(distribution)}
