"""Compare the rule engine and authentication model on held-out synthetic data."""

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from .auth_model import (
    MODEL_THRESHOLD,
    MODEL_VERSION,
    TRAIN_COUNT,
    TRAIN_SEED,
    analyze_authentication,
)
from .main import Base, Event, EventInput, detect
from .telemetry import generate_events


EVAL_SEED = 31415
EVAL_COUNT = 2000
RULE_THRESHOLD = 25


def metrics(actual: list[bool], predictions: list[bool]) -> dict:
    pairs = list(zip(actual, predictions, strict=True))
    tp = sum(label and prediction for label, prediction in pairs)
    fp = sum(not label and prediction for label, prediction in pairs)
    tn = sum(not label and not prediction for label, prediction in pairs)
    fn = sum(label and not prediction for label, prediction in pairs)
    return {
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "f1": 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else None,
    }


def evaluate() -> dict:
    engine = create_engine("sqlite://")
    labels, rule_predictions, model_predictions = [], [], []
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            for row in generate_events(EVAL_COUNT, EVAL_SEED):
                payload = EventInput.model_validate(row["event"])
                event = Event(id=row["sample_id"], **payload.model_dump())
                db.add(event)
                db.flush()
                # Evaluate chronologically, with only the current and past events.
                score, _, _, _ = detect(event, db)
                analysis = analyze_authentication(event.type, event.failed_logins)
                labels.append(row["ground_truth"]["suspicious"])
                rule_predictions.append(score >= RULE_THRESHOLD)
                model_predictions.append(analysis["flagged"])
    finally:
        engine.dispose()

    return {
        "training": {"seed": TRAIN_SEED, "samples": TRAIN_COUNT},
        "holdout": {"seed": EVAL_SEED, "samples": EVAL_COUNT, "positives": sum(labels)},
        "rules": {"threshold": RULE_THRESHOLD, **metrics(labels, rule_predictions)},
        "model": {
            "version": MODEL_VERSION,
            "threshold": MODEL_THRESHOLD,
            **metrics(labels, model_predictions),
        },
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
