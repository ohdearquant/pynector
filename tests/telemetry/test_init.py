"""Tests for dependency detection in the telemetry module."""

import pytest
import sys
from unittest.mock import patch


def test_opentelemetry_detection_available():
    """Test that OpenTelemetry is correctly detected when available."""
    # Mock sys.modules to simulate OpenTelemetry being available
    with patch.dict(sys.modules, {
        'opentelemetry': pytest.importorskip('opentelemetry', reason="OpenTelemetry not installed"),
        'opentelemetry.trace': pytest.importorskip('opentelemetry.trace', reason="OpenTelemetry trace not installed")
    }):
        # Re-import to trigger detection
        import importlib
        with patch.dict(sys.modules, {'pynector.telemetry': None}):
            from src.pynector import telemetry
            importlib.reload(telemetry)
            assert telemetry.HAS_OPENTELEMETRY is True


def test_opentelemetry_detection_unavailable():
    """Test that OpenTelemetry is correctly detected as unavailable."""
    # Mock sys.modules to simulate OpenTelemetry being unavailable
    with patch.dict(sys.modules, {
        'opentelemetry': None,
        'opentelemetry.trace': None
    }):
        # Re-import to trigger detection
        import importlib
        with patch.dict(sys.modules, {'pynector.telemetry': None}):
            from src.pynector import telemetry
            importlib.reload(telemetry)
            assert telemetry.HAS_OPENTELEMETRY is False
            
            # Verify that StatusCode and Status are defined
            from src.pynector.telemetry import StatusCode, Status
            assert hasattr(StatusCode, 'ERROR')
            assert hasattr(StatusCode, 'OK')
            
            status = Status(StatusCode.ERROR)
            assert status.status_code == StatusCode.ERROR


def test_structlog_detection_available():
    """Test that structlog is correctly detected when available."""
    # Mock sys.modules to simulate structlog being available
    with patch.dict(sys.modules, {
        'structlog': pytest.importorskip('structlog', reason="structlog not installed")
    }):
        # Re-import to trigger detection
        import importlib
        with patch.dict(sys.modules, {'pynector.telemetry': None}):
            from src.pynector import telemetry
            importlib.reload(telemetry)
            assert telemetry.HAS_STRUCTLOG is True


def test_structlog_detection_unavailable():
    """Test that structlog is correctly detected as unavailable."""
    # Mock sys.modules to simulate structlog being unavailable
    with patch.dict(sys.modules, {
        'structlog': None
    }):
        # Re-import to trigger detection
        import importlib
        with patch.dict(sys.modules, {'pynector.telemetry': None}):
            from src.pynector import telemetry
            importlib.reload(telemetry)
            assert telemetry.HAS_STRUCTLOG is False


def test_get_telemetry():
    """Test that get_telemetry returns the correct objects."""
    from src.pynector.telemetry import get_telemetry
    from src.pynector.telemetry.facade import TracingFacade, LoggingFacade
    
    tracer, logger = get_telemetry("test")
    
    assert isinstance(tracer, TracingFacade)
    assert isinstance(logger, LoggingFacade)
    assert tracer.name == "test"
    assert logger.name == "test"