"""A supervised, smoothed histogram model for synthetic authentication events."""

from collections import Counter
from functools import lru_cache

from .telemetry import generate_events


MODEL_VERSION = "auth-retry-histogram-v1"
TRAIN_SEED = 42
TRAIN_COUNT = 5000
MODEL_THRESHOLD = 0.5
AUTH_TYPES = {"failed_login", "normal_login", "brute_force"}
MAX_RETRY_BUCKET = 30


def retry_bucket(failed_logins: int) -> int:
    return min(failed_logins, MAX_RETRY_BUCKET)


@lru_cache(maxsize=1)
def trained_probabilities() -> tuple[float, ...]:
    observations = Counter()
    suspicious = Counter()
    for row in generate_events(TRAIN_COUNT, TRAIN_SEED):
        bucket = retry_bucket(row["event"]["failed_logins"])
        observations[bucket] += 1
        suspicious[bucket] += row["ground_truth"]["suspicious"]

    # Add one observation per class to keep probabilities finite at the extremes.
    return tuple(
        (suspicious[bucket] + 1) / (observations[bucket] + 2)
        for bucket in range(MAX_RETRY_BUCKET + 1)
    )


def analyze_authentication(event_type: str, failed_logins: int) -> dict | None:
    if event_type not in AUTH_TYPES:
        return None

    probability = trained_probabilities()[retry_bucket(failed_logins)]
    return {
        "model_version": MODEL_VERSION,
        "suspicion_score": round(probability, 4),
        "flagged": probability >= MODEL_THRESHOLD,
    }
