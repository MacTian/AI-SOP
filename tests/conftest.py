"""Shared test fixtures."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the FastAPI app (with lifespan)."""
    from backend.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_sop_data():
    """Sample SOP creation payload."""
    return {
        "sop_id": "test_sop",
        "name": "Test SOP",
        "version": "1.0",
        "description": "A test SOP",
        "max_total_duration": 600,
        "steps": [
            {
                "step_id": "step_1",
                "name": "Pick up item",
                "order": 0,
                "timeout": 60,
                "rule": {
                    "expected_objects": ["person", "hand"],
                    "min_confidence": 0.5,
                    "required_count": 1,
                },
            },
            {
                "step_id": "step_2",
                "name": "Place item",
                "order": 1,
                "timeout": 60,
                "rule": {
                    "expected_objects": ["box"],
                    "min_confidence": 0.5,
                    "required_count": 1,
                },
            },
        ],
    }
