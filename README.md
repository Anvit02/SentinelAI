# SentinelAI — AI Security Operations Agent

A local-first security investigation system with a FastAPI backend, deterministic risk scoring, persistent investigation reports, and a React dashboard.

**Status · v0.3.1 prototype in active development.** The demo uses synthetic security events.

## Run the backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Open http://localhost:8000/docs.

The backend uses SQLite by default. To use PostgreSQL, copy `.env.example` to
`.env` in the project root, set a local demo password, and run
`docker compose up -d --wait db` from that root. Before starting Uvicorn,
set `DATABASE_URL` in the backend terminal to
`postgresql+psycopg://sentinel:<password>@127.0.0.1:5432/sentinelai`.
Use the same password in both places and URL-encode it in the connection
string if it contains reserved characters. An existing PostgreSQL volume
retains the password set when it was first initialized.

## Run the dashboard

```bash
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173.

Try **Investigate** on the **Brute Force** demo event (`evt-002`).
The report shows the rule score, supporting evidence, recommended analyst
actions, and the authentication model result. To reopen or update a saved
case, use **Investigations** in the sidebar.

## Run checks

- From `backend`, run `python -m pytest -q`.
- From `frontend`, run `npm run build`.

## What works

- View seeded synthetic security events
- Run investigations with explainable evidence and rule-based risk scores
- Reopen saved reports and update analyst review status
- Inspect recommended actions without executing them
- Health check and automated backend tests

## Generate labeled telemetry

From `backend`, run:

```bash
python -m app.telemetry --count 500 --seed 42 --output telemetry.jsonl
```

The command creates a new JSONL file. Each row contains a sample ID, an
`event` payload compatible with `POST /api/events`, and separate
`ground_truth` labels for offline evaluation. The same seed and count produce
the same output. Legitimate and suspicious retry bursts overlap in failed
login counts so that a count threshold alone cannot perfectly separate them.
Generation works offline and leaves the dashboard database untouched.
Use the `event` field alone as detector input to keep labels out of scoring.

## Evaluate authentication detection

From `backend`, run `python -m app.evaluate_detection`. The evaluator compares
the existing rule engine at 25 points against a supervised retry-count
histogram model at a score of 0.5, and an unsupervised Isolation Forest.
Both models train on 5,000 synthetic events and the evaluator
evaluates chronologically on 2,000 events generated with a different seed.
The run reports confusion counts, precision, recall, and F1. It uses
an in-memory database.

| Detector | Precision | Recall | F1 |
| --- | ---: | ---: | ---: |
| Existing rules | 100.0% | 44.3% | 61.4% |
| Authentication model | 83.1% | 56.3% | 67.1% |
| Isolation Forest | 58.9% | 48.4% | 53.1% |

Isolation Forest uses log-transformed failed attempts and the account's
count of failed-login events in the 15 minutes ending at that event. It
fits without labels and uses a 10% training contamination setting.
Higher scores indicate more unusual activity. On the held-out synthetic
set, ROC AUC was 0.875 and average precision was 0.403. The report
displays the score, threshold, and feature values for analyst review.
Backfilled telemetry can change historical features when reports reopen.

Authentication investigation reports show the model's result alongside the
rule score. The model reads the retry count and learns from synthetic labels.
Its score describes patterns in the generator and has no established
calibration on operational logs. The existing rules still determine report
severity and recommendations. Report reads compute the supplemental analysis
from the event, so existing reports work without a database migration.

## Roadmap

The next milestone is supervised threat classification. Later milestones
cover hybrid scoring and explainability, an investigation copilot, retrieval,
streaming, deployment, and portfolio preparation.

**Safety:** All identities and events are synthetic. Recommendations never automatically block accounts or IPs.
