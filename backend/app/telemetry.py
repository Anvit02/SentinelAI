"""Generate labeled authentication telemetry for offline detection evaluation."""

import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path


START = datetime(2026, 1, 1, tzinfo=timezone.utc)
COUNTRIES = ("US", "CA", "GB", "DE", "JP")


def generate_events(count: int, seed: int):
    """Yield JSON-compatible records with API payloads and separate ground truth."""
    if count < 1:
        raise ValueError("count must be positive")

    rng = random.Random(seed)
    timestamp = START
    home_countries = [rng.choice(COUNTRIES) for _ in range(40)]
    for index in range(count):
        account = rng.randrange(len(home_countries))
        country = home_countries[account]
        scenario = rng.choices(
            ("routine", "password_typo", "legitimate_retry_burst", "suspicious_retry_burst"),
            weights=(65, 15, 10, 10),
        )[0]

        failed_logins = 0
        if scenario == "password_typo":
            failed_logins = rng.randint(1, 4)
        elif scenario == "legitimate_retry_burst":
            failed_logins = rng.randint(5, 18)
        elif scenario == "suspicious_retry_burst":
            failed_logins = rng.randint(8, 30)
            country = rng.choice(COUNTRIES)

        timestamp += timedelta(seconds=rng.randint(15, 180))
        yield {
            "sample_id": f"sample-{index + 1:06d}",
            "event": {
                "user": f"analyst-{account:02d}@example.test",
                "type": "failed_login" if failed_logins else "normal_login",
                "ip": f"192.0.2.{rng.randint(1, 254)}",
                "country": country,
                "failed_logins": failed_logins,
                "occurred_at": timestamp.isoformat(),
            },
            "ground_truth": {
                "suspicious": scenario == "suspicious_retry_burst",
                "scenario": scenario,
            },
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, required=True, help="New JSONL file")
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be positive")

    try:
        with args.output.open("x", encoding="utf-8", newline="\n") as output:
            for record in generate_events(args.count, args.seed):
                output.write(json.dumps(record) + "\n")
    except OSError as error:
        parser.exit(1, f"{parser.prog}: {error}\n")


if __name__ == "__main__":
    main()
