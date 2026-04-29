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


# --- SOP API ---

def test_sop_list(client):
    resp = client.get("/api/sop/list")
    assert resp.status_code == 200
    data = resp.json()
    assert "sops" in data
    # Should have example_assembly
    sop_ids = [s["sop_id"] for s in data["sops"]]
    assert "example_assembly" in sop_ids


def test_sop_get(client):
    resp = client.get("/api/sop/example_assembly")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sop_id"] == "example_assembly"
    assert data["name"] == "PCB Assembly Example"
    assert len(data["steps"]) == 5


def test_sop_get_not_found(client):
    resp = client.get("/api/sop/nonexistent")
    assert resp.status_code == 404


def test_sop_create_and_delete(client, sample_sop_data):
    # Create
    resp = client.post("/api/sop/", json=sample_sop_data)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    # Verify it exists
    resp = client.get("/api/sop/test_sop")
    assert resp.status_code == 200
    assert resp.json()["sop_id"] == "test_sop"

    # Delete
    resp = client.delete("/api/sop/test_sop")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

    # Verify it's gone
    resp = client.get("/api/sop/test_sop")
    assert resp.status_code == 404


def test_sop_delete_not_found(client):
    resp = client.delete("/api/sop/nonexistent")
    assert resp.status_code == 404


# --- Monitor API ---

def test_monitor_status(client):
    resp = client.get("/api/monitor/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "active_sops" in data


def test_monitor_alerts(client):
    resp = client.get("/api/monitor/alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert "alerts" in data


def test_monitor_records(client):
    resp = client.get("/api/monitor/records")
    assert resp.status_code == 200
    data = resp.json()
    assert "records" in data


def test_monitor_records_with_limit(client):
    resp = client.get("/api/monitor/records?limit=5")
    assert resp.status_code == 200


# --- Alert Config API ---

def test_alert_rules_empty(client):
    resp = client.get("/api/alerts/rules")
    assert resp.status_code == 200
    assert "rules" in resp.json()


def test_alert_rules_crud(client):
    # Create
    rule = {
        "sop_id": "test",
        "step_id": "s1",
        "level": "warning",
        "escalation_count": 3,
    }
    resp = client.post("/api/alerts/rules", json=rule)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    # List
    resp = client.get("/api/alerts/rules")
    rules = resp.json()["rules"]
    assert any(r["sop_id"] == "test" for r in rules)

    # Delete
    resp = client.delete("/api/alerts/rules/test/s1")
    assert resp.status_code == 200


# --- Stats API ---

def test_stats_summary(client):
    resp = client.get("/api/stats/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_events" in data
    assert "status_breakdown" in data


def test_stats_detections(client):
    resp = client.get("/api/stats/detections?minutes=5")
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data


def test_stats_timeline(client):
    resp = client.get("/api/stats/timeline?minutes=5")
    assert resp.status_code == 200
    data = resp.json()
    assert "timeline" in data


def test_stats_sop_completion(client):
    resp = client.get("/api/stats/sop/example_assembly/completion")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sop_id"] == "example_assembly"
    assert "total_events" in data
    assert "completion_rate" in data


# --- Video API ---

def test_video_snapshot_no_camera(client):
    # Camera may or may not be available, just check endpoint exists
    resp = client.get("/video/snapshot")
    # Should return either an image or an error JSON
    assert resp.status_code == 200
