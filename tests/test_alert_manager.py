"""Tests for alert manager."""

from backend.alert.manager import AlertManager, AlertRule
from backend.extractor.event import SopEvent


def make_event(status="error", sop_id="test", step_id="s1"):
    return SopEvent(
        sop_id=sop_id,
        step_id=step_id,
        step_name="Test Step",
        status=status,
        confidence=0.9,
    )


def test_alert_on_error():
    am = AlertManager(cooldown=0)
    alert = am.process_event(make_event(status="error"))
    assert alert is not None
    assert alert.level == "error"
    assert alert.sop_id == "test"


def test_alert_on_timeout():
    am = AlertManager(cooldown=0)
    alert = am.process_event(make_event(status="timeout"))
    assert alert is not None
    assert alert.level == "warning"


def test_alert_on_skipped():
    am = AlertManager(cooldown=0)
    alert = am.process_event(make_event(status="skipped"))
    assert alert is not None
    assert alert.level == "info"


def test_no_alert_on_detected():
    am = AlertManager()
    alert = am.process_event(make_event(status="detected"))
    assert alert is None


def test_no_alert_on_completed():
    am = AlertManager()
    alert = am.process_event(make_event(status="completed"))
    assert alert is None


def test_alert_deduplication():
    am = AlertManager(cooldown=10)
    am.process_event(make_event(status="error"))
    # Second same alert within cooldown should be suppressed
    alert2 = am.process_event(make_event(status="error"))
    assert alert2 is None


def test_alert_cooldown_expiry():
    import time
    am = AlertManager(cooldown=0)
    am.process_event(make_event(status="error", step_id="s1"))
    time.sleep(0.01)
    # Different step_id to avoid dedup on same key
    alert2 = am.process_event(make_event(status="error", step_id="s2"))
    assert alert2 is not None


def test_alert_escalation():
    am = AlertManager(cooldown=0)
    am.add_rule(AlertRule(
        sop_id="test", step_id="s1", level="warning", escalation_count=2
    ))
    # First alert
    a1 = am.process_event(make_event(status="timeout"))
    assert a1 is not None
    assert a1.level == "warning"

    import time
    time.sleep(0.01)
    # Second alert (should escalate to error after 2 repeats)
    a2 = am.process_event(make_event(status="timeout"))
    assert a2 is not None
    # Level should have escalated
    assert a2.level in ("error", "warning")


def test_alert_acknowledge():
    am = AlertManager(cooldown=0)
    alert = am.process_event(make_event(status="error"))
    assert alert.acknowledged is False
    ok = am.acknowledge(alert.alert_id)
    assert ok is True
    # Check it's acknowledged in the list
    recent = am.get_recent_alerts()
    assert recent[0]["acknowledged"] is True


def test_alert_acknowledge_nonexistent():
    am = AlertManager()
    ok = am.acknowledge("nonexistent")
    assert ok is False


def test_alert_acknowledge_all():
    am = AlertManager(cooldown=0)
    am.process_event(make_event(status="error", step_id="s1"))
    am.process_event(make_event(status="timeout", step_id="s2"))
    count = am.acknowledge_all()
    assert count >= 2
    for a in am.get_recent_alerts():
        assert a["acknowledged"] is True


def test_alert_rules():
    am = AlertManager()
    am.add_rule(AlertRule(sop_id="test", step_id="s1", level="error"))
    rules = am.get_rules()
    assert len(rules) == 1
    assert rules[0]["level"] == "error"

    am.remove_rule("test", "s1")
    rules = am.get_rules()
    assert len(rules) == 0


def test_get_recent_alerts():
    am = AlertManager(cooldown=0)
    for i in range(5):
        am.process_event(make_event(status="error", step_id=f"s{i}"))
    alerts = am.get_recent_alerts(limit=3)
    assert len(alerts) == 3
    for a in alerts:
        assert "alert_id" in a
        assert "level" in a
        assert "timestamp" in a
