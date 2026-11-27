"""Unsupervised authentication anomaly scoring from label-free telemetry."""

from collections import defaultdict, deque
from datetime import datetime, timedelta
from functools import lru_cache
from math import log1p

from sklearn.ensemble import IsolationForest

from .auth_model import AUTH_TYPES, TRAIN_COUNT, TRAIN_SEED
from .telemetry import generate_events


MODEL_VERSION = "auth-isolation-forest-v1"
CONTAMINATION = 0.1
HISTORY_WINDOW = timedelta(minutes=15)


def features(failed_logins: int, recent_failure_events: int) -> tuple[float, float]:
    return log1p(failed_logins), log1p(recent_failure_events)


def training_features():
    history = defaultdict(deque)
    for row in generate_events(TRAIN_COUNT, TRAIN_SEED):
        event = row["event"]
        timestamp = datetime.fromisoformat(event["occurred_at"])
        failures = history[event["user"]]
        while failures and failures[0] < timestamp - HISTORY_WINDOW:
            failures.popleft()
        if event["type"] == "failed_login":
            failures.append(timestamp)
        yield features(event["failed_logins"], len(failures))


@lru_cache(maxsize=1)
def trained_forest() -> IsolationForest:
    model = IsolationForest(contamination=CONTAMINATION, random_state=TRAIN_SEED)
    return model.fit(list(training_features()))


@lru_cache(maxsize=1024)
def anomaly_score(failed_logins: int, recent_failure_events: int) -> float:
    # Invert sklearn's score so higher values indicate more unusual activity.
    return float(-trained_forest().score_samples([features(failed_logins, recent_failure_events)])[0])


def analyze_anomaly(event_type: str, failed_logins: int, recent_failure_events: int) -> dict | None:
    if event_type not in AUTH_TYPES:
        return None
    score = anomaly_score(failed_logins, recent_failure_events)
    threshold = float(-trained_forest().offset_)
    return {
        "model_version": MODEL_VERSION,
        "anomaly_score": round(score, 4),
        "threshold": round(threshold, 4),
        "flagged": score > threshold,
        "features": {
            "failed_logins": failed_logins,
            "recent_failure_events": recent_failure_events,
        },
    }
