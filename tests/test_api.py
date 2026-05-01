"""Tests for API endpoints."""

import pytest


# --- Root & Health ---

def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "AI SOP Monitor"
    assert data["status"] == "running"


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "camera" in data
    assert "inference" in data


# --- Auth API ---

def test_auth_login(client):
    resp = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_auth_login_wrong_password(client):
    resp = client.post("/api/auth/login", data={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_auth_me(client, auth_headers):
    resp = client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "admin"
    assert data["role"] == "admin"


def test_auth_me_no_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


# --- SOP API ---

def test_sop_list(client, auth_headers):
    resp = client.get("/api/sop/list", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "sops" in data
    sop_ids = [s["sop_id"] for s in data["sops"]]
    assert "example_assembly" in sop_ids


def test_sop_get(client, auth_headers):
    resp = client.get("/api/sop/example_assembly", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["sop_id"] == "example_assembly"
    assert data["name"] == "PCB Assembly Example"
    assert len(data["steps"]) == 5


def test_sop_get_not_found(client, auth_headers):
    resp = client.get("/api/sop/nonexistent", headers=auth_headers)
    assert resp.status_code == 404


def test_sop_create_and_delete(client, auth_headers, sample_sop_data):
    # Create
    resp = client.post("/api/sop/", json=sample_sop_data, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    # Verify it exists
    resp = client.get("/api/sop/test_sop", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["sop_id"] == "test_sop"

    # Delete
    resp = client.delete("/api/sop/test_sop", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

    # Verify it's gone
    resp = client.get("/api/sop/test_sop", headers=auth_headers)
    assert resp.status_code == 404


def test_sop_delete_not_found(client, auth_headers):
    resp = client.delete("/api/sop/nonexistent", headers=auth_headers)
    assert resp.status_code == 404


# --- Monitor API ---

def test_monitor_status(client, auth_headers):
    resp = client.get("/api/monitor/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "active_sops" in data


def test_monitor_alerts(client, auth_headers):
    resp = client.get("/api/monitor/alerts", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "alerts" in data


def test_monitor_records(client, auth_headers):
    resp = client.get("/api/monitor/records", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "records" in data


def test_monitor_records_with_limit(client, auth_headers):
    resp = client.get("/api/monitor/records?limit=5", headers=auth_headers)
    assert resp.status_code == 200


# --- Alert Config API ---

def test_alert_rules_empty(client, auth_headers):
    resp = client.get("/api/alerts/rules", headers=auth_headers)
    assert resp.status_code == 200
    assert "rules" in resp.json()


def test_alert_rules_crud(client, auth_headers):
    # Create
    rule = {
        "sop_id": "test",
        "step_id": "s1",
        "level": "warning",
        "escalation_count": 3,
    }
    resp = client.post("/api/alerts/rules", json=rule, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    # List
    resp = client.get("/api/alerts/rules", headers=auth_headers)
    rules = resp.json()["rules"]
    assert any(r["sop_id"] == "test" for r in rules)

    # Delete
    resp = client.delete("/api/alerts/rules/test/s1", headers=auth_headers)
    assert resp.status_code == 200


# --- Stats API ---

def test_stats_summary(client, auth_headers):
    resp = client.get("/api/stats/summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_events" in data
    assert "status_breakdown" in data


def test_stats_detections(client, auth_headers):
    resp = client.get("/api/stats/detections?minutes=5", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data


def test_stats_timeline(client, auth_headers):
    resp = client.get("/api/stats/timeline?minutes=5", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "timeline" in data


def test_stats_sop_completion(client, auth_headers):
    resp = client.get("/api/stats/sop/example_assembly/completion", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["sop_id"] == "example_assembly"
    assert "total_events" in data
    assert "completion_rate" in data


# --- Video API ---

def test_video_snapshot_no_camera(client):
    # Video endpoints are public (no auth required)
    resp = client.get("/video/snapshot")
    assert resp.status_code == 200


# --- Template API ---

def test_template_list(client, auth_headers):
    resp = client.get("/api/sop/templates/list", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "templates" in data
    template_ids = [t["sop_id"] for t in data["templates"]]
    assert "electronics_assembly" in template_ids
    assert "packaging" in template_ids


def test_template_get(client, auth_headers):
    resp = client.get("/api/sop/templates/electronics_assembly", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["sop_id"] == "electronics_assembly"
    assert data["name"] == "电子组装流程"
    assert len(data["steps"]) == 5


def test_template_get_not_found(client, auth_headers):
    resp = client.get("/api/sop/templates/nonexistent", headers=auth_headers)
    assert resp.status_code == 404


def test_template_use(client, auth_headers):
    resp = client.post("/api/sop/templates/packaging/use", json={
        "sop_id": "my_packaging",
        "name": "My Packaging SOP",
        "description": "Custom packaging",
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["sop_id"] == "my_packaging"
    assert data["step_count"] == 6

    # Verify the new SOP exists
    resp = client.get("/api/sop/my_packaging", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "My Packaging SOP"

    # Cleanup
    client.delete("/api/sop/my_packaging", headers=auth_headers)


def test_template_use_not_found(client, auth_headers):
    resp = client.post("/api/sop/templates/nonexistent/use", json={
        "sop_id": "test",
        "name": "Test",
    }, headers=auth_headers)
    assert resp.status_code == 404


# --- Training API ---

def test_training_status_idle(client, auth_headers):
    resp = client.get("/api/training/status", headers=auth_headers)
    assert resp.status_code == 200


def test_training_start_and_stop(client, auth_headers):
    # Start
    resp = client.post("/api/training/start", json={
        "sop_name": "Test Training",
        "sop_description": "Testing",
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "recording"

    # Status should show recording
    resp = client.get("/api/training/status", headers=auth_headers)
    assert resp.json()["status"] == "recording"

    # Stop (no frames recorded, but session exists)
    resp = client.post("/api/training/stop", headers=auth_headers)
    assert resp.status_code == 200


def test_training_result_empty(client, auth_headers):
    resp = client.get("/api/training/result", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data or "steps" in data


def test_training_reset(client, auth_headers):
    resp = client.post("/api/training/reset", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "reset"
