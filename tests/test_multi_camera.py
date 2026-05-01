"""Tests for multi-camera manager."""

from unittest.mock import MagicMock, patch
from backend.camera.multi_camera import MultiCameraManager


def test_parse_device_ids_default():
    """Default single camera device."""
    mgr = MultiCameraManager()
    with patch("backend.camera.multi_camera.settings") as mock_settings:
        mock_settings.camera_devices = ""
        mock_settings.camera_device = 0
        assert mgr._parse_device_ids() == [0]


def test_parse_device_ids_multi():
    """Multiple camera devices from config."""
    mgr = MultiCameraManager()
    with patch("backend.camera.multi_camera.settings") as mock_settings:
        mock_settings.camera_devices = "0,1,2"
        assert mgr._parse_device_ids() == [0, 1, 2]


def test_parse_device_ids_whitespace():
    """Device IDs with whitespace."""
    mgr = MultiCameraManager()
    with patch("backend.camera.multi_camera.settings") as mock_settings:
        mock_settings.camera_devices = " 0 , 1 , 2 "
        assert mgr._parse_device_ids() == [0, 1, 2]


def test_get_active_cameras_empty():
    """No cameras started."""
    mgr = MultiCameraManager()
    assert mgr.get_active_cameras() == []


def test_get_camera_none():
    """Getting camera that doesn't exist."""
    mgr = MultiCameraManager()
    assert mgr.get_camera(99) is None


def test_get_engine_none():
    """Getting engine that doesn't exist."""
    mgr = MultiCameraManager()
    assert mgr.get_engine(99) is None


def test_callback_set():
    """Setting and invoking callback."""
    mgr = MultiCameraManager()
    callback = MagicMock()
    mgr.set_callback(callback)

    # Simulate a detection result
    mock_result = MagicMock()
    mgr._on_result(0, mock_result)
    callback.assert_called_once_with(0, mock_result)


def test_callback_error_handling():
    """Callback errors should be caught."""
    mgr = MultiCameraManager()
    callback = MagicMock(side_effect=Exception("test error"))
    mgr.set_callback(callback)

    # Should not raise
    mgr._on_result(0, MagicMock())


def test_stop_empty():
    """Stopping with no cameras should not raise."""
    mgr = MultiCameraManager()
    mgr.stop()  # Should not raise
