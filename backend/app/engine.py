from dataclasses import dataclass
from typing import Any

EVENTS = [
    {"id": "evt-001", "user": "alex@example.test", "type": "impossible_travel", "ip": "198.51.100.24", "country": "RU", "failed_logins": 37, "privileged_token": True, "description": "Rapid geo-change with privileged token creation"},
    {"id": "evt-002", "user": "jordan@example.test", "type": "brute_force", "ip": "203.0.113.10", "country": "US", "failed_logins": 22, "privileged_token": False, "description": "Repeated failed authentication attempts"},
    {"id": "evt-003", "user": "sam@example.test", "type": "normal_login", "ip": "192.0.2.8", "country": "US", "failed_logins": 0, "privileged_token": False, "description": "Successful login from known location"},
    {"id": "evt-004", "user": "taylor@example.test", "type": "token_creation", "ip": "203.0.113.55", "country": "US", "failed_logins": 3, "privileged_token": True, "description": "Privileged token created after failed logins"},
]

def investigate(event: dict[str, Any]) -> dict[str, Any]:
    score = 0
    evidence = []
    if event["type"] == "impossible_travel":
        score += 45
        evidence.append({"signal": "Impossible travel", "points": 45, "detail": "Synthetic geo-velocity anomaly"})
    if event["failed_logins"] >= 20:
        score += 25
        evidence.append({"signal": "Authentication failures", "points": 25, "detail": f'{event["failed_logins"]} failed attempts'})
    elif event["failed_logins"] >= 5:
        score += 10
        evidence.append({"signal": "Authentication failures", "points": 10, "detail": f'{event["failed_logins"]} failed attempts'})
    if event["privileged_token"]:
        score += 24
        evidence.append({"signal": "Privileged token", "points": 24, "detail": "New privileged token detected"})
    if event["type"] == "brute_force":
        score += 30
        evidence.append({"signal": "Brute force pattern", "points": 30, "detail": "Repeated authentication failures"})
    score = min(100, score)
    severity = "critical" if score >= 85 else "high" if score >= 60 else "medium" if score >= 30 else "low"
    actions = ["Review activity and verify identity"] if score < 60 else [
        "Request analyst review", "Consider token revocation", "Consider credential reset"
    ]
    return {
        "event_id": event["id"], "user": event["user"], "risk_score": score,
        "severity": severity, "evidence": evidence, "recommended_actions": actions,
        "status": "awaiting_human_review", "auto_actions_executed": False,
        "summary": f'{severity.upper()} risk for {event["user"]}: {len(evidence)} corroborating signal(s).',
        "scoring_method": "Deterministic prototype rules, not a calibrated probability."
    }
