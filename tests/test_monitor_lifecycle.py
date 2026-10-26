"""Lifecycle tests: start a SOP → feed detections → observe real state changes.

These tests cover the wiring that used to be missing entirely (P0-2): the
`/api/monitor/start` endpoint, the timeout supervisor loop, and the alert chain.
They deliberately go through the rule engine instead of poking the state machine
directly, so a broken `_load_sop_rules()` wiring would fail them.
"""

import time
import uuid

import pytest

import backend.main as main_mod
from backend.inference.detector import Detection, DetectionResult


def _create_sop(client, auth_headers, sop_id, step_timeout=60):
    """Create a 2-step SOP with the given per-step timeout.

    The expected objects are deliberately NOT the ones the mock detector emits
    ("person" / "tool"), so a live camera running the mock pipeline during the
    test session cannot complete these steps behind our back.
    """
    payload = {
        "sop_id": sop_id,
        "name": f"Lifecycle {sop_id}",
        "version": "1.0",
        "description": "created by lifecycle tests",
        "steps": [
            {
                "step_id": "s1",
                "name": "Step One",
                "order": 0,
                "timeout": step_timeout,
                "rule": {"expected_objects": ["chair"], "min_confidence": 0.5},
            },
            {
                "step_id": "s2",
                "name": "Step Two",
                "order": 1,
                "timeout": 600,
                "rule": {"expected_objects": ["box"], "min_confidence": 0.5},
            },
        ],
    }
    resp = client.post("/api/sop/", json=payload, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    return payload


@pytest.fixture
def lifecycle_sop(client, auth_headers):
    """A freshly created SOP, deleted again afterwards."""
    sop_id = f"lifecycle_{uuid.uuid4().hex[:8]}"
    _create_sop(client, auth_headers, sop_id)
    try:
        yield sop_id
    finally:
        client.post(f"/api/monitor/stop/{sop_id}", headers=auth_headers)
        client.delete(f"/api/sop/{sop_id}", headers=auth_headers)


def _feed(sop_id, class_name, times):
    """Push `times` frames of one detection class through rules → state machine."""
    events = []
    for _ in range(times):
        result = DetectionResult(detections=[
            Detection(class_id=0, class_name=class_name, confidence=0.9, bbox=(0, 0, 10, 10))
        ])
        produced = main_mod.rule_engine.evaluate(sop_id, result, [])
        for event in produced:
            main_mod.state_machine.process_event(event)
        events.extend(produced)
    return events


# --- API surface ---

def test_start_requires_auth(client, lifecycle_sop):
    resp = client.post(f"/api/monitor/start/{lifecycle_sop}")
    assert resp.status_code == 401


def test_start_unknown_sop_returns_404(client, auth_headers):
    resp = client.post("/api/monitor/start/does_not_exist", headers=auth_headers)
    assert resp.status_code == 404


def test_start_and_stop_sop(client, auth_headers, lifecycle_sop):
    resp = client.post(f"/api/monitor/start/{lifecycle_sop}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "started"
    assert body["sop_id"] == lifecycle_sop
    assert body["step_statuses"]["s1"] == "active"

    # The instance must be visible through the status endpoint
    status = client.get("/api/monitor/status", headers=auth_headers).json()
    active_ids = [s["sop_id"] for s in status["active_sops"]]
    assert lifecycle_sop in active_ids

    # Starting twice is a conflict, not a silent restart
    resp = client.post(f"/api/monitor/start/{lifecycle_sop}", headers=auth_headers)
    assert resp.status_code == 409

    resp = client.post(f"/api/monitor/stop/{lifecycle_sop}", headers=auth_headers)
    assert resp.status_code == 200
    status = client.get("/api/monitor/status", headers=auth_headers).json()
    assert lifecycle_sop not in [s["sop_id"] for s in status["active_sops"]]

    # Stopping again is a 404
    resp = client.post(f"/api/monitor/stop/{lifecycle_sop}", headers=auth_headers)
    assert resp.status_code == 404


# --- End-to-end progress ---

def test_detections_advance_and_complete_steps(client, auth_headers, lifecycle_sop):
    """Start → feed N frames → steps complete (the whole P0-2 chain)."""
    started = client.post(
        f"/api/monitor/start/{lifecycle_sop}", headers=auth_headers
    ).json()
    required_s1 = started["step_hit_progress"]["s1"]["required"]
    required_s2 = started["step_hit_progress"]["s2"]["required"]

    # Step 1: expected_objects ["chair"] → detection of "chair"
    _feed(lifecycle_sop, "chair", required_s1)
    state = client.get(f"/api/monitor/sop/{lifecycle_sop}/state", headers=auth_headers).json()
    assert state["step_statuses"]["s1"] == "completed", state
    assert state["step_statuses"]["s2"] == "active", state

    # Step 2: expected_objects ["box"] → resolves to COCO "suitcase"/"backpack"/"handbag"
    _feed(lifecycle_sop, "suitcase", required_s2)
    state = client.get(f"/api/monitor/sop/{lifecycle_sop}/state", headers=auth_headers).json()
    assert state["step_statuses"]["s2"] == "completed", state
    assert state["progress"] == 1.0
    assert state["is_complete"] is True


def test_unrelated_detections_do_not_advance(client, auth_headers, lifecycle_sop):
    client.post(f"/api/monitor/start/{lifecycle_sop}", headers=auth_headers)
    _feed(lifecycle_sop, "airplane", 10)  # matches no rule
    state = client.get(f"/api/monitor/sop/{lifecycle_sop}/state", headers=auth_headers).json()
    assert state["step_statuses"] == {"s1": "active", "s2": "pending"}


@pytest.fixture
def no_background_sweep():
    """Pause the periodic timeout supervisor so a manual sweep is deterministic."""
    task = main_mod._timeout_task
    assert task is not None, "timeout supervisor was never scheduled"
    main_mod._loop.call_soon_threadsafe(task.cancel)
    time.sleep(0.2)  # let the cancellation take effect
    yield


# --- Timeout supervision ---

def test_timeout_sweep_emits_event_and_alert(client, auth_headers, no_background_sweep):
    sop_id = f"timeout_{uuid.uuid4().hex[:8]}"
    _create_sop(client, auth_headers, sop_id, step_timeout=0)
    try:
        client.post(f"/api/monitor/start/{sop_id}", headers=auth_headers)

        emitted = main_mod._process_timeouts()
        matching = [(e, a) for e, a in emitted if e.sop_id == sop_id]
        assert matching, "timeout sweep produced no event"

        event, alert = matching[0]
        assert event.status == "timeout"
        assert event.step_id == "s1"
        assert alert is not None and alert.level == "warning"

        # Timed-out step is terminal, and the SOP keeps going with step 2
        state = client.get(f"/api/monitor/sop/{sop_id}/state", headers=auth_headers).json()
        assert state["step_statuses"]["s1"] == "timeout"
        assert state["step_statuses"]["s2"] == "active"

        # A second sweep must not re-emit the same timeout
        again = [(e, a) for e, a in main_mod._process_timeouts() if e.sop_id == sop_id]
        assert again == []

        # ... and it reached both the alert list and the record table
        alerts = client.get("/api/monitor/alerts", headers=auth_headers).json()["alerts"]
        assert any(a["sop_id"] == sop_id and a["level"] == "warning" for a in alerts)

        records = client.get(
            f"/api/monitor/records?sop_id={sop_id}", headers=auth_headers
        ).json()["records"]
        assert any(r["status"] == "timeout" and r["step_id"] == "s1" for r in records)
    finally:
        client.post(f"/api/monitor/stop/{sop_id}", headers=auth_headers)
        client.delete(f"/api/sop/{sop_id}", headers=auth_headers)


def test_timeout_supervisor_runs_in_background(client, auth_headers):
    """The sweep must be scheduled on startup, not only callable by hand."""
    task = main_mod._timeout_task
    assert task is not None and not task.done()

    sop_id = f"bg_timeout_{uuid.uuid4().hex[:8]}"
    _create_sop(client, auth_headers, sop_id, step_timeout=0)
    try:
        client.post(f"/api/monitor/start/{sop_id}", headers=auth_headers)

        deadline = time.time() + 8
        while time.time() < deadline:
            state = client.get(
                f"/api/monitor/sop/{sop_id}/state", headers=auth_headers
            ).json()
            if state["step_statuses"]["s1"] == "timeout":
                return
            time.sleep(0.25)
        pytest.fail("background timeout supervisor never fired")
    finally:
        client.post(f"/api/monitor/stop/{sop_id}", headers=auth_headers)
        client.delete(f"/api/sop/{sop_id}", headers=auth_headers)


def test_timeout_supervisor_runs_in_background(client, auth_headers):
    """The sweep must be scheduled on startup, not only callable by hand."""
    sop_id = f"bg_timeout_{uuid.uuid4().hex[:8]}"
    _create_sop(client, auth_headers, sop_id, step_timeout=0)
    try:
        client.post(f"/api/monitor/start/{sop_id}", headers=auth_headers)

        deadline = time.time() + 8
        while time.time() < deadline:
            state = client.get(
                f"/api/monitor/sop/{sop_id}/state", headers=auth_headers
            ).json()
            if state["step_statuses"]["s1"] == "timeout":
                return
            time.sleep(0.25)
        pytest.fail("background timeout supervisor never fired")
    finally:
        client.post(f"/api/monitor/stop/{sop_id}", headers=auth_headers)
        client.delete(f"/api/sop/{sop_id}", headers=auth_headers)
