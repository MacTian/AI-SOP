"""Tests for SOP manager (YAML CRUD)."""

import tempfile
from pathlib import Path

from backend.sop.schema import SopDefinition, SopStep, StepRule
from backend.sop.sop_manager import SopManager


def make_test_sop(sop_id="test_mgr"):
    return SopDefinition(
        sop_id=sop_id,
        name="Test SOP",
        version="1.0",
        description="For testing",
        steps=[
            SopStep(
                step_id="s1", name="Step 1", order=0,
                rule=StepRule(expected_objects=["hand"], min_confidence=0.6),
            ),
            SopStep(
                step_id="s2", name="Step 2", order=1,
                rule=StepRule(expected_objects=["tool"]),
            ),
        ],
    )


def test_sop_manager_save_and_load():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = SopManager(sop_dir=tmpdir)
        sop = make_test_sop()
        mgr.save(sop)

        loaded = mgr.load("test_mgr")
        assert loaded.sop_id == "test_mgr"
        assert loaded.name == "Test SOP"
        assert len(loaded.steps) == 2
        assert loaded.steps[0].rule.expected_objects == ["hand"]


def test_sop_manager_list():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = SopManager(sop_dir=tmpdir)
        mgr.save(make_test_sop("sop_a"))
        mgr.save(make_test_sop("sop_b"))

        sops = mgr.list_sops()
        ids = [s["sop_id"] for s in sops]
        assert "sop_a" in ids
        assert "sop_b" in ids


def test_sop_manager_delete():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = SopManager(sop_dir=tmpdir)
        mgr.save(make_test_sop())
        assert mgr.delete("test_mgr") is True
        assert mgr.delete("test_mgr") is False


def test_sop_manager_load_not_found():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = SopManager(sop_dir=tmpdir)
        try:
            mgr.load("nonexistent")
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            pass


def test_sop_manager_roundtrip():
    """Save → load → save → load should preserve all fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = SopManager(sop_dir=tmpdir)
        original = make_test_sop()
        mgr.save(original)

        loaded = mgr.load("test_mgr")
        mgr.save(loaded)

        reloaded = mgr.load("test_mgr")
        assert loaded.sop_id == reloaded.sop_id
        assert loaded.name == reloaded.name
        assert len(loaded.steps) == len(reloaded.steps)
        for s1, s2 in zip(loaded.steps, reloaded.steps):
            assert s1.step_id == s2.step_id
            assert s1.rule.expected_objects == s2.rule.expected_objects
