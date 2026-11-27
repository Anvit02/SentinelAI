import os
os.environ['DATABASE_URL'] = 'sqlite:///./sentinelai_test.db'
from fastapi.testclient import TestClient
from app.main import app

def test_end_to_end():
    with TestClient(app) as client:
        assert client.get('/api/health').status_code == 200
        assert len(client.get('/api/events').json()) >= 4
        critical = client.post('/api/investigations/evt-001')
        assert critical.status_code == 200
        assert critical.json()['risk_score'] == 94
        assert critical.json()['auto_actions_executed'] is False
        assert critical.json()['authentication_analysis'] is None
        new = client.post('/api/events', json={'user':'tester@example.test','type':'failed_login','ip':'192.0.2.10','country':'US'})
        assert new.status_code == 201
        event_id = new.json()['id']
        report = client.post('/api/investigations/' + event_id)
        assert report.status_code == 200
        analysis = report.json()['authentication_analysis']
        assert analysis['model_version'] == 'auth-retry-histogram-v1'
        assert analysis['flagged'] is False
        assert 0 <= analysis['suspicion_score'] < 0.5
        saved = client.get('/api/investigations/' + report.json()['id'])
        assert saved.json()['authentication_analysis'] == analysis
        assert client.post('/api/investigations/' + event_id).json()['id'] == report.json()['id']
        assert client.patch('/api/investigations/' + critical.json()['id'], json={'status':'resolved'}).json()['status'] == 'resolved'
        assert client.get('/api/stats').json()['investigations'] >= 2
        assert client.post('/api/investigations/missing').status_code == 404
