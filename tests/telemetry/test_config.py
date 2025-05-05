"""Tests for the configuration module."""

import pytest
import os
from unittest.mock import patch, MagicMock


def test_get_env_bool():
    """Test get_env_bool function."""
    from src.pynector.telemetry.config import get_env_bool
    
    # Test with environment variable set to true
    with patch.dict(os.environ, {"TEST_BOOL": "true"}):
        assert get_env_bool("TEST_BOOL") is True
    
    # Test with environment variable set to false
    with patch.dict(os.environ, {"TEST_BOOL": "false"}):
        assert get_env_bool("TEST_BOOL") is False
    
    # Test with environment variable set to 1
    with patch.dict(os.environ, {"TEST_BOOL": "1"}):
        assert get_env_bool("TEST_BOOL") is True
    
    # Test with environment variable set to 0
    with patch.dict(os.environ, {"TEST_BOOL": "0"}):
        assert get_env_bool("TEST_BOOL") is False
    
    # Test with environment variable not set
    with patch.dict(os.environ, {}, clear=True):
        assert get_env_bool("TEST_BOOL") is False
        assert get_env_bool("TEST_BOOL", True) is True


def test_get_env_dict():
    """Test get_env_dict function."""
    from src.pynector.telemetry.config import get_env_dict
    
    # Test with environment variable set
    with patch.dict(os.environ, {"TEST_DICT": "key1=value1,key2=value2"}):
        result = get_env_dict("TEST_DICT")
        assert result == {"key1": "value1", "key2": "value2"}
    
    # Test with environment variable not set
    with patch.dict(os.environ, {}, clear=True):
        result = get_env_dict("TEST_DICT")
        assert result == {}
        
        # Test with default value
        result = get_env_dict("TEST_DICT", {"default_key": "default_value"})
        assert result == {"default_key": "default_value"}


@pytest.mark.parametrize("has_opentelemetry,has_structlog", [
    (True, True),
    (True, False),
    (False, True),
    (False, False)
])
def test_configure_telemetry(has_opentelemetry, has_structlog):
    """Test configure_telemetry function."""
    # Mock dependencies availability
    with patch('src.pynector.telemetry.config.HAS_OPENTELEMETRY', has_opentelemetry), \
         patch('src.pynector.telemetry.config.HAS_STRUCTLOG', has_structlog):
        
        if not (has_opentelemetry or has_structlog):
            # If no dependencies are available, should return False
            from src.pynector.telemetry.config import configure_telemetry
            assert configure_telemetry() is False
        else:
            if has_opentelemetry:
                # Mock OpenTelemetry modules
                mock_resource = MagicMock()
                mock_resource_create = MagicMock(return_value=mock_resource)
                mock_tracer_provider = MagicMock()
                mock_tracer_provider_class = MagicMock(return_value=mock_tracer_provider)
                mock_set_tracer_provider = MagicMock()
                mock_configure_exporters = MagicMock()
                
                with patch('src.pynector.telemetry.config.Resource.create', mock_resource_create), \
                     patch('src.pynector.telemetry.config.TracerProvider', mock_tracer_provider_class), \
                     patch('src.pynector.telemetry.config.trace.set_tracer_provider', mock_set_tracer_provider), \
                     patch('src.pynector.telemetry.config._configure_exporters', mock_configure_exporters):
                    
                    from src.pynector.telemetry.config import configure_telemetry
                    
                    # Test with default values
                    with patch.dict(os.environ, {}, clear=True):
                        result = configure_telemetry()
                        
                        assert result is True
                        mock_resource_create.assert_called_once_with({"service.name": "unknown_service"})
                        mock_tracer_provider_class.assert_called_once_with(resource=mock_resource)
                        mock_set_tracer_provider.assert_called_once_with(mock_tracer_provider)
                        mock_configure_exporters.assert_called_once_with(mock_tracer_provider, None)
                    
                    # Test with custom values
                    mock_resource_create.reset_mock()
                    mock_tracer_provider_class.reset_mock()
                    mock_set_tracer_provider.reset_mock()
                    mock_configure_exporters.reset_mock()
                    
                    result = configure_telemetry(
                        service_name="test-service",
                        resource_attributes={"key": "value"},
                        trace_enabled=True,
                        trace_exporters=["console"]
                    )
                    
                    assert result is True
                    mock_resource_create.assert_called_once_with({"key": "value", "service.name": "test-service"})
                    mock_tracer_provider_class.assert_called_once_with(resource=mock_resource)
                    mock_set_tracer_provider.assert_called_once_with(mock_tracer_provider)
                    mock_configure_exporters.assert_called_once_with(mock_tracer_provider, ["console"])
                    
                    # Test with trace_enabled=False
                    mock_resource_create.reset_mock()
                    mock_tracer_provider_class.reset_mock()
                    mock_set_tracer_provider.reset_mock()
                    mock_configure_exporters.reset_mock()
                    
                    result = configure_telemetry(trace_enabled=False)
                    
                    assert result is False
                    mock_resource_create.assert_not_called()
                    mock_tracer_provider_class.assert_not_called()
                    mock_set_tracer_provider.assert_not_called()
                    mock_configure_exporters.assert_not_called()
            
            if has_structlog:
                # Mock structlog module
                mock_configure_structlog = MagicMock()
                
                with patch('src.pynector.telemetry.config._configure_structlog', mock_configure_structlog):
                    from src.pynector.telemetry.config import configure_telemetry
                    
                    # Test with default values
                    mock_configure_structlog.reset_mock()
                    result = configure_telemetry()
                    
                    assert result is (True if has_opentelemetry else False)
                    mock_configure_structlog.assert_called_once_with("INFO", None)
                    
                    # Test with custom values
                    mock_configure_structlog.reset_mock()
                    
                    result = configure_telemetry(
                        log_level="DEBUG",
                        log_processors=["custom_processor"]
                    )
                    
                    assert result is (True if has_opentelemetry else False)
                    mock_configure_structlog.assert_called_once_with("DEBUG", ["custom_processor"])


def test_configure_exporters():
    """Test _configure_exporters function."""
    # Mock OpenTelemetry modules
    mock_tracer_provider = MagicMock()
    mock_batch_span_processor = MagicMock()
    mock_batch_span_processor_class = MagicMock(return_value=mock_batch_span_processor)
    
    # Mock exporters
    mock_otlp_exporter = MagicMock()
    mock_otlp_exporter_class = MagicMock(return_value=mock_otlp_exporter)
    mock_console_exporter = MagicMock()
    mock_console_exporter_class = MagicMock(return_value=mock_console_exporter)
    mock_zipkin_exporter = MagicMock()
    mock_zipkin_exporter_class = MagicMock(return_value=mock_zipkin_exporter)
    
    with patch('src.pynector.telemetry.config.BatchSpanProcessor', mock_batch_span_processor_class), \
         patch('src.pynector.telemetry.config.OTLPSpanExporter', mock_otlp_exporter_class), \
         patch('src.pynector.telemetry.config.ConsoleSpanExporter', mock_console_exporter_class), \
         patch('src.pynector.telemetry.config.ZipkinExporter', mock_zipkin_exporter_class):
        
        from src.pynector.telemetry.config import _configure_exporters
        
        # Test with default exporters (otlp)
        with patch.dict(os.environ, {}, clear=True):
            _configure_exporters(mock_tracer_provider)
            
            mock_otlp_exporter_class.assert_called_once_with()
            mock_batch_span_processor_class.assert_called_once_with(mock_otlp_exporter)
            mock_tracer_provider.add_span_processor.assert_called_once_with(mock_batch_span_processor)
        
        # Test with OTLP endpoint
        mock_otlp_exporter_class.reset_mock()
        mock_batch_span_processor_class.reset_mock()
        mock_tracer_provider.add_span_processor.reset_mock()
        
        with patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317"}):
            _configure_exporters(mock_tracer_provider)
            
            mock_otlp_exporter_class.assert_called_once_with(endpoint="http://localhost:4317")
            mock_batch_span_processor_class.assert_called_once_with(mock_otlp_exporter)
            mock_tracer_provider.add_span_processor.assert_called_once_with(mock_batch_span_processor)
        
        # Test with console exporter
        mock_otlp_exporter_class.reset_mock()
        mock_console_exporter_class.reset_mock()
        mock_batch_span_processor_class.reset_mock()
        mock_tracer_provider.add_span_processor.reset_mock()
        
        _configure_exporters(mock_tracer_provider, ["console"])
        
        mock_otlp_exporter_class.assert_not_called()
        mock_console_exporter_class.assert_called_once_with()
        mock_batch_span_processor_class.assert_called_once_with(mock_console_exporter)
        mock_tracer_provider.add_span_processor.assert_called_once_with(mock_batch_span_processor)
        
        # Test with zipkin exporter
        mock_zipkin_exporter_class.reset_mock()
        mock_batch_span_processor_class.reset_mock()
        mock_tracer_provider.add_span_processor.reset_mock()
        
        _configure_exporters(mock_tracer_provider, ["zipkin"])
        
        mock_zipkin_exporter_class.assert_called_once_with()
        mock_batch_span_processor_class.assert_called_once_with(mock_zipkin_exporter)
        mock_tracer_provider.add_span_processor.assert_called_once_with(mock_batch_span_processor)
        
        # Test with zipkin endpoint
        mock_zipkin_exporter_class.reset_mock()
        mock_batch_span_processor_class.reset_mock()
        mock_tracer_provider.add_span_processor.reset_mock()
        
        with patch.dict(os.environ, {"OTEL_EXPORTER_ZIPKIN_ENDPOINT": "http://localhost:9411/api/v2/spans"}):
            _configure_exporters(mock_tracer_provider, ["zipkin"])
            
            mock_zipkin_exporter_class.assert_called_once_with(endpoint="http://localhost:9411/api/v2/spans")
            mock_batch_span_processor_class.assert_called_once_with(mock_zipkin_exporter)
            mock_tracer_provider.add_span_processor.assert_called_once_with(mock_batch_span_processor)
        
        # Test with multiple exporters
        mock_otlp_exporter_class.reset_mock()
        mock_console_exporter_class.reset_mock()
        mock_zipkin_exporter_class.reset_mock()
        mock_batch_span_processor_class.reset_mock()
        mock_tracer_provider.add_span_processor.reset_mock()
        
        _configure_exporters(mock_tracer_provider, ["otlp", "console", "zipkin"])
        
        assert mock_otlp_exporter_class.call_count == 1
        assert mock_console_exporter_class.call_count == 1
        assert mock_zipkin_exporter_class.call_count == 1
        assert mock_batch_span_processor_class.call_count == 3
        assert mock_tracer_provider.add_span_processor.call_count == 3


def test_configure_structlog():
    """Test _configure_structlog function."""
    # Mock structlog modules
    mock_structlog = MagicMock()
    mock_logging = MagicMock()
    
    with patch('src.pynector.telemetry.config.structlog', mock_structlog), \
         patch('src.pynector.telemetry.config.logging', mock_logging):
        
        from src.pynector.telemetry.config import _configure_structlog
        
        # Test with default values
        _configure_structlog("INFO")
        
        mock_logging.basicConfig.assert_called_once_with(
            format="%(message)s",
            level=mock_logging.INFO,
        )
        
        # Verify processors
        assert mock_structlog.contextvars.merge_contextvars in mock_structlog.configure.call_args[1]['processors']
        assert mock_structlog.processors.add_log_level in mock_structlog.configure.call_args[1]['processors']
        assert mock_structlog.processors.TimeStamper in mock_structlog.configure.call_args[1]['processors']
        assert mock_structlog.processors.JSONRenderer in mock_structlog.configure.call_args[1]['processors']
        
        # Test with custom processors
        mock_structlog.reset_mock()
        mock_logging.reset_mock()
        
        custom_processor = MagicMock()
        _configure_structlog("DEBUG", [custom_processor])
        
        mock_logging.basicConfig.assert_called_once_with(
            format="%(message)s",
            level=mock_logging.DEBUG,
        )
        
        # Verify processors include custom processor
        assert custom_processor in mock_structlog.configure.call_args[1]['processors']