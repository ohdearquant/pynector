# Test Implementation: Optional Observability

**Issue:** #3\
**Author:** pynector-implementer\
**Date:** 2025-05-05\
**Status:** Draft

## 1. Introduction

This Test Implementation (TI) document outlines the testing strategy for the
Optional Observability feature as specified in [TDS-3.md](../tds/TDS-3.md) and
implemented according to [IP-3.md](../ip/IP-3.md). The testing approach follows
Test-Driven Development (TDD) principles and aims to achieve >80% code coverage,
with special attention to testing both with and without optional dependencies.

## 2. Test Structure

The tests will be organized in the following directory structure:

```
tests/
└── telemetry/
    ├── __init__.py
    ├── test_config.py         # Tests for configuration functions
    ├── test_context.py        # Tests for context propagation utilities
    ├── test_facade.py         # Tests for telemetry facades
    ├── test_logging.py        # Tests for logging implementations
    ├── test_tracing.py        # Tests for tracing implementations
    └── test_integration.py    # Integration tests
```

## 3. Testing Framework and Tools

The tests will use the following tools:

- **pytest**: Primary testing framework
- **pytest-asyncio**: For testing async code
- **pytest-cov**: For measuring code coverage
- **pytest-mock**: For mocking dependencies
- **importlib-metadata**: For dynamically controlling available packages

## 4. Test Cases

### 4.1 Dependency Detection Tests (`test_init.py`)

These tests will verify that the dependency detection logic correctly identifies
whether optional dependencies are available.

````python
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
        importlib.reload(sys.modules['pynector.telemetry'])
        from pynector.telemetry import HAS_OPENTELEMETRY

        assert HAS_OPENTELEMETRY is True

def test_opentelemetry_detection_unavailable():
    """Test that OpenTelemetry is correctly detected as unavailable."""
    # Mock sys.modules to simulate OpenTelemetry being unavailable
    with patch.dict(sys.modules, {
        'opentelemetry': None,
        'opentelemetry.trace': None
    }):
        # Re-import to trigger detection
        import importlib
        importlib.reload(sys.modules['pynector.telemetry'])
        from pynector.telemetry import HAS_OPENTELEMETRY

        assert HAS_OPENTELEMETRY is False

        # Verify that StatusCode and Status are defined
        from pynector.telemetry import StatusCode, Status
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
        importlib.reload(sys.modules['pynector.telemetry'])
        from pynector.telemetry import HAS_STRUCTLOG

        assert HAS_STRUCTLOG is True

def test_structlog_detection_unavailable():
    """Test that structlog is correctly detected as unavailable."""
    # Mock sys.modules to simulate structlog being unavailable
    with patch.dict(sys.modules, {
        'structlog': None
    }):
        # Re-import to trigger detection
        import importlib
        importlib.reload(sys.modules['pynector.telemetry'])
        from pynector.telemetry import HAS_STRUCTLOG

        assert HAS_STRUCTLOG is False

def test_get_telemetry():
    """Test that get_telemetry returns the correct objects."""
    from pynector.telemetry import get_telemetry
    from pynector.telemetry.facade import TracingFacade, LoggingFacade

    tracer, logger = get_telemetry("test")

    assert isinstance(tracer, TracingFacade)
    assert isinstance(logger, LoggingFacade)
    assert tracer.name == "test"
    assert logger.name == "test"
### 4.2 No-op Tracing Tests (`test_tracing.py`)

These tests will verify that the no-op tracing implementations work correctly.

```python
import pytest
import asyncio
from pynector.telemetry.tracing import NoOpSpan, AsyncSpanWrapper

def test_noop_span_init():
    """Test NoOpSpan initialization."""
    span = NoOpSpan("test_span", {"key": "value"})

    assert span.name == "test_span"
    assert span.attributes == {"key": "value"}

    # Test with default values
    span = NoOpSpan()
    assert span.name == ""
    assert span.attributes == {}

def test_noop_span_context_manager():
    """Test NoOpSpan as a context manager."""
    with NoOpSpan("test_span") as span:
        assert isinstance(span, NoOpSpan)
        span.set_attribute("key", "value")
        assert span.attributes["key"] == "value"

@pytest.mark.asyncio
async def test_noop_span_async_context_manager():
    """Test NoOpSpan as an async context manager."""
    async with NoOpSpan("test_span") as span:
        assert isinstance(span, NoOpSpan)
        span.set_attribute("key", "value")
        assert span.attributes["key"] == "value"

def test_noop_span_methods():
    """Test NoOpSpan methods."""
    span = NoOpSpan("test_span")

    # Test set_attribute
    span.set_attribute("key", "value")
    assert span.attributes["key"] == "value"

    # Test add_event (no-op, should not raise)
    span.add_event("test_event", {"event_key": "event_value"})

    # Test record_exception (no-op, should not raise)
    try:
        raise ValueError("Test exception")
    except ValueError as e:
        span.record_exception(e)

    # Test set_status (no-op, should not raise)
    from pynector.telemetry import Status, StatusCode
    span.set_status(Status(StatusCode.ERROR))

@pytest.mark.asyncio
async def test_async_span_wrapper():
    """Test AsyncSpanWrapper."""
    # Create a mock span
    class MockSpan:
        def __init__(self):
            self.entered = False
            self.exited = False

        def __enter__(self):
            self.entered = True
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.exited = True

    mock_span = MockSpan()
    wrapper = AsyncSpanWrapper(mock_span)

    async with wrapper as span:
        assert span is mock_span
        assert mock_span.entered is True
        assert mock_span.exited is False

    assert mock_span.exited is True

@pytest.mark.asyncio
async def test_async_span_wrapper_with_token():
    """Test AsyncSpanWrapper with a token."""
    from unittest.mock import patch

    # Create a mock span
    class MockSpan:
        def __init__(self):
            self.entered = False
            self.exited = False

        def __enter__(self):
            self.entered = True
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.exited = True

### 4.3 No-op Logging Tests (`test_logging.py`)

These tests will verify that the no-op logging implementations work correctly.

```python
import pytest
from pynector.telemetry.logging import NoOpLogger

def test_noop_logger_init():
    """Test NoOpLogger initialization."""
    logger = NoOpLogger("test_logger")
    assert logger.name == "test_logger"

    # Test with default value
    logger = NoOpLogger()
    assert logger.name == ""

def test_noop_logger_methods():
    """Test NoOpLogger methods."""
    logger = NoOpLogger("test_logger")

    # All methods should be no-ops and not raise exceptions
    logger.debug("test_event", key="value")
    logger.info("test_event", key="value")
    logger.warning("test_event", key="value")
    logger.error("test_event", key="value")
    logger.critical("test_event", key="value")
````

### 4.4 Telemetry Facade Tests (`test_facade.py`)

These tests will verify that the telemetry facades work correctly, both with and
without optional dependencies.

````python
import pytest
import sys
from unittest.mock import patch, MagicMock

# Tests with OpenTelemetry available
@pytest.mark.parametrize("has_opentelemetry", [True, False])
def test_tracing_facade_init(has_opentelemetry):
    """Test TracingFacade initialization."""
    # Mock OpenTelemetry availability
    with patch('pynector.telemetry.facade.HAS_OPENTELEMETRY', has_opentelemetry):
        if has_opentelemetry:
            # Mock the trace module
            mock_tracer = MagicMock()
            mock_get_tracer = MagicMock(return_value=mock_tracer)
            with patch('pynector.telemetry.facade.trace.get_tracer', mock_get_tracer):
                from pynector.telemetry.facade import TracingFacade
                tracer = TracingFacade("test_tracer")

                assert tracer.name == "test_tracer"
                assert tracer.tracer == mock_tracer
                mock_get_tracer.assert_called_once_with("test_tracer")
        else:
            from pynector.telemetry.facade import TracingFacade
            tracer = TracingFacade("test_tracer")

            assert tracer.name == "test_tracer"
            assert tracer.tracer is None

@pytest.mark.parametrize("has_opentelemetry", [True, False])
def test_tracing_facade_start_span(has_opentelemetry):
    """Test TracingFacade.start_span."""
    # Mock OpenTelemetry availability
    with patch('pynector.telemetry.facade.HAS_OPENTELEMETRY', has_opentelemetry):
        if has_opentelemetry:
            # Mock the trace module
            mock_span = MagicMock()
            mock_tracer = MagicMock()
            mock_tracer.start_span.return_value = mock_span
            mock_get_tracer = MagicMock(return_value=mock_tracer)
            with patch('pynector.telemetry.facade.trace.get_tracer', mock_get_tracer):
                from pynector.telemetry.facade import TracingFacade
                tracer = TracingFacade("test_tracer")

                span = tracer.start_span("test_span", {"key": "value"})

                assert span == mock_span
                mock_tracer.start_span.assert_called_once_with("test_span", attributes={"key": "value"})
        else:
            from pynector.telemetry.facade import TracingFacade
            from pynector.telemetry.tracing import NoOpSpan
            tracer = TracingFacade("test_tracer")

            span = tracer.start_span("test_span", {"key": "value"})

@pytest.mark.parametrize("has_opentelemetry", [True, False])
def test_tracing_facade_start_as_current_span(has_opentelemetry):
    """Test TracingFacade.start_as_current_span."""
    # Mock OpenTelemetry availability
    with patch('pynector.telemetry.facade.HAS_OPENTELEMETRY', has_opentelemetry):
        if has_opentelemetry:
            # Mock the trace module
            mock_span = MagicMock()
            mock_tracer = MagicMock()
            mock_tracer.start_as_current_span.return_value = mock_span
            mock_get_tracer = MagicMock(return_value=mock_tracer)
            with patch('pynector.telemetry.facade.trace.get_tracer', mock_get_tracer):
                from pynector.telemetry.facade import TracingFacade
                tracer = TracingFacade("test_tracer")

                span = tracer.start_as_current_span("test_span", {"key": "value"})

                assert span == mock_span
                mock_tracer.start_as_current_span.assert_called_once_with("test_span", attributes={"key": "value"})
        else:
            from pynector.telemetry.facade import TracingFacade
            from pynector.telemetry.tracing import NoOpSpan
            tracer = TracingFacade("test_tracer")

            span = tracer.start_as_current_span("test_span", {"key": "value"})

            assert isinstance(span, NoOpSpan)
            assert span.name == "test_span"
            assert span.attributes == {"key": "value"}

@pytest.mark.asyncio
@pytest.mark.parametrize("has_opentelemetry", [True, False])
async def test_tracing_facade_start_async_span(has_opentelemetry):
    """Test TracingFacade.start_async_span."""
    # Mock OpenTelemetry availability
    with patch('pynector.telemetry.facade.HAS_OPENTELEMETRY', has_opentelemetry):
        if has_opentelemetry:
            # Mock the trace module
            mock_span = MagicMock()
            mock_tracer = MagicMock()
            mock_tracer.start_span.return_value = mock_span
            mock_get_tracer = MagicMock(return_value=mock_tracer)
            with patch('pynector.telemetry.facade.trace.get_tracer', mock_get_tracer):
                from pynector.telemetry.facade import TracingFacade
                from pynector.telemetry.tracing import AsyncSpanWrapper
                tracer = TracingFacade("test_tracer")

                span_wrapper = await tracer.start_async_span("test_span", {"key": "value"})

                assert isinstance(span_wrapper, AsyncSpanWrapper)
                assert span_wrapper.span == mock_span
                mock_tracer.start_span.assert_called_once_with("test_span", attributes={"key": "value"})
        else:
            from pynector.telemetry.facade import TracingFacade
            from pynector.telemetry.tracing import NoOpSpan
            tracer = TracingFacade("test_tracer")

            span = await tracer.start_async_span("test_span", {"key": "value"})

            assert isinstance(span, NoOpSpan)
            assert span.name == "test_span"
            assert span.attributes == {"key": "value"}

@pytest.mark.parametrize("has_structlog", [True, False])
def test_logging_facade_init(has_structlog):
    """Test LoggingFacade initialization."""
    # Mock structlog availability
    with patch('pynector.telemetry.facade.HAS_STRUCTLOG', has_structlog):
        if has_structlog:
            # Mock the structlog module
            mock_logger = MagicMock()
            mock_get_logger = MagicMock(return_value=mock_logger)
            with patch('pynector.telemetry.facade.structlog.get_logger', mock_get_logger):
                from pynector.telemetry.facade import LoggingFacade
                logger = LoggingFacade("test_logger")

                assert logger.name == "test_logger"
                assert logger.logger == mock_logger
                mock_get_logger.assert_called_once_with("test_logger")
        else:
            from pynector.telemetry.facade import LoggingFacade
            from pynector.telemetry.logging import NoOpLogger
            logger = LoggingFacade("test_logger")

            assert logger.name == "test_logger"
            assert isinstance(logger.logger, NoOpLogger)

### 4.5 Context Propagation Tests (`test_context.py`)

These tests will verify that the context propagation utilities work correctly.

```python
import pytest
import asyncio
from unittest.mock import patch, MagicMock
from pynector.telemetry.context import traced_async_operation, traced_gather, traced_task_group

@pytest.mark.asyncio
async def test_traced_async_operation():
    """Test traced_async_operation context manager."""
    # Create a mock tracer
    mock_span = MagicMock()
    mock_tracer = MagicMock()
    mock_tracer.start_as_current_async_span = MagicMock()
    mock_tracer.start_as_current_async_span.return_value.__aenter__ = MagicMock(return_value=mock_span)
    mock_tracer.start_as_current_async_span.return_value.__aexit__ = MagicMock(return_value=None)

    # Test successful operation
    async with traced_async_operation(mock_tracer, "test_operation", {"key": "value"}) as span:
        assert span == mock_span
        # Perform some operation
        result = 42

    mock_tracer.start_as_current_async_span.assert_called_once_with("test_operation", attributes={"key": "value"})

    # Test operation with exception
    with pytest.raises(ValueError):
@pytest.mark.asyncio
@pytest.mark.parametrize("has_opentelemetry", [True, False])
async def test_traced_gather(has_opentelemetry):
    """Test traced_gather function."""
    # Mock OpenTelemetry availability
    with patch('pynector.telemetry.context.HAS_OPENTELEMETRY', has_opentelemetry):
        if has_opentelemetry:
            # Mock the context module
            mock_token = MagicMock()
            mock_context = MagicMock()
            mock_attach = MagicMock(return_value=mock_token)
            mock_detach = MagicMock()
            mock_get_current = MagicMock(return_value=mock_context)

            # Create a mock tracer
            mock_span = MagicMock()
            mock_tracer = MagicMock()
            mock_tracer.start_as_current_async_span = MagicMock()
            mock_tracer.start_as_current_async_span.return_value.__aenter__ = MagicMock(return_value=mock_span)
            mock_tracer.start_as_current_async_span.return_value.__aexit__ = MagicMock(return_value=None)

            with patch('pynector.telemetry.context.attach', mock_attach), \
                 patch('pynector.telemetry.context.detach', mock_detach), \
                 patch('pynector.telemetry.context.get_current', mock_get_current):

                # Create test coroutines
                async def coro1():
                    return 1

                async def coro2():
                    return 2

                # Test traced_gather
                results = await traced_gather(mock_tracer, [coro1(), coro2()], "test_gather")

                assert results == [1, 2]
                mock_tracer.start_as_current_async_span.assert_called_once_with("test_gather")
                assert mock_attach.call_count == 2
                assert mock_detach.call_count == 2
        else:
            # Create test coroutines
            async def coro1():
                return 1

            async def coro2():
                return 2

            # Test traced_gather without OpenTelemetry
            results = await traced_gather(MagicMock(), [coro1(), coro2()], "test_gather")

            assert results == [1, 2]

### 4.6 Configuration Tests (`test_config.py`)

These tests will verify that the configuration functions work correctly.

```python
import pytest
import os
from unittest.mock import patch, MagicMock
from pynector.telemetry.config import get_env_bool, get_env_dict, configure_telemetry

def test_get_env_bool():
    """Test get_env_bool function."""
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
    with patch('pynector.telemetry.config.HAS_OPENTELEMETRY', has_opentelemetry), \
         patch('pynector.telemetry.config.HAS_STRUCTLOG', has_structlog):

        if not (has_opentelemetry or has_structlog):
            # If no dependencies are available, should return False
            assert configure_telemetry() is False
        else:
            if has_opentelemetry:
                # Mock OpenTelemetry modules
                mock_resource = MagicMock()
                mock_resource_create = MagicMock(return_value=mock_resource)
                mock_tracer_provider = MagicMock()
                mock_tracer_provider_class = MagicMock(return_value=mock_tracer_provider)

                with patch('pynector.telemetry.config.Resource.create', mock_resource_create), \
                     patch('pynector.telemetry.config.TracerProvider', mock_tracer_provider_class), \
                     patch('pynector.telemetry.config.trace.set_tracer_provider') as mock_set_tracer_provider, \
                     patch('pynector.telemetry.config._configure_exporters') as mock_configure_exporters:

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

            if has_structlog:
                # Mock structlog module
                with patch('pynector.telemetry.config._configure_structlog') as mock_configure_structlog:
                    # Test with default values
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
````

### 4.7 Integration Tests (`test_integration.py`)

These tests will verify that all components work together correctly.

````python
import pytest
import asyncio
from unittest.mock import patch, MagicMock
from pynector.telemetry import get_telemetry, configure_telemetry

@pytest.mark.asyncio
@pytest.mark.parametrize("has_opentelemetry,has_structlog", [
    (True, True),
    (True, False),
    (False, True),
    (False, False)
])
async def test_telemetry_integration(has_opentelemetry, has_structlog):
    """Test that all telemetry components work together correctly."""
    # Mock dependencies availability
    with patch('pynector.telemetry.HAS_OPENTELEMETRY', has_opentelemetry), \
         patch('pynector.telemetry.facade.HAS_OPENTELEMETRY', has_opentelemetry), \
         patch('pynector.telemetry.context.HAS_OPENTELEMETRY', has_opentelemetry), \
         patch('pynector.telemetry.config.HAS_OPENTELEMETRY', has_opentelemetry), \
         patch('pynector.telemetry.HAS_STRUCTLOG', has_structlog), \
         patch('pynector.telemetry.facade.HAS_STRUCTLOG', has_structlog), \
         patch('pynector.telemetry.config.HAS_STRUCTLOG', has_structlog):

        # Configure telemetry
        configure_telemetry(service_name="test-service")

        # Get tracer and logger
        tracer, logger = get_telemetry("test-module")

        # Test synchronous tracing
        with tracer.start_as_current_span("test-span", {"key": "value"}) as span:
            # Log with structured data
            logger.info("test-event", data="test-data")
## 5. Test Coverage

The tests are designed to achieve >80% code coverage across all components. Coverage will be measured using pytest-cov and reported during CI runs.

```bash
pytest --cov=pynector.telemetry tests/telemetry/
````

Special attention will be paid to testing both with and without optional
dependencies, ensuring that the library works correctly in all scenarios.

## 6. Test Execution

Tests will be executed as part of the CI pipeline and can also be run locally
using pytest:

```bash
# Run all tests
pytest tests/telemetry/

# Run specific test file
pytest tests/telemetry/test_facade.py

# Run with coverage
pytest --cov=pynector.telemetry tests/telemetry/

# Generate coverage report
pytest --cov=pynector.telemetry --cov-report=html tests/telemetry/
```

### 6.1 Testing with and without Optional Dependencies

To test both with and without optional dependencies, the tests will use mocking
to simulate the presence or absence of dependencies. In addition, the CI
pipeline should run the tests in two configurations:

1. With all optional dependencies installed
2. With no optional dependencies installed

This ensures that the library works correctly in all scenarios.

```bash
# Test with all dependencies
pip install -e ".[observability-full]"
pytest tests/telemetry/

# Test without optional dependencies
pip install -e .
pytest tests/telemetry/
```

## 7. References

1. Technical Design Specification: Optional Observability (TDS-3.md) (search:
   internal-document)
2. Implementation Plan: Optional Observability (IP-3.md) (search:
   internal-document)
3. Research Report: OpenTelemetry Tracing and Structured Logging in Async Python
   Libraries (RR-3.md) (search: internal-document)
4. OpenTelemetry Python Documentation (search:
   exa-opentelemetry-python.readthedocs.io)
5. OpenTelemetry Context Propagation (search:
   exa-opentelemetry.io/docs/concepts/context-propagation/)
6. Structlog Documentation (search: exa-www.structlog.org/en/stable/)
7. pytest Documentation (search: exa-docs.pytest.org)
8. pytest-asyncio Documentation (search: exa-pytest-asyncio.readthedocs.io)
9. pytest-mock Documentation (search: exa-pytest-mock.readthedocs.io)

           # Set span attribute
           span.set_attribute("result", "success")

       # Test asynchronous tracing
       async with tracer.start_as_current_async_span("test-async-span") as span:
           # Log with structured data
           logger.info("test-async-event", data="test-async-data")

           # Set span attribute
           span.set_attribute("async-result", "success")

           # Test error handling
           try:
               raise ValueError("Test error")
           except ValueError as e:
               logger.error("test-error", error=str(e))
               span.record_exception(e)

       # Test context propagation
       from pynector.telemetry.context import traced_async_operation, traced_gather

       async def test_operation():
           return "success"

       async with traced_async_operation(tracer, "test-operation") as span:
           result = await test_operation()
           span.set_attribute("operation-result", result)

       # Test parallel operations
       async def operation1():
           return "result1"

       async def operation2():
           return "result2"

       results = await traced_gather(tracer, [operation1(), operation2()], "parallel-operations")
       assert results == ["result1", "result2"]

```
    async with traced_async_operation(mock_tracer, "test_operation") as span:
        assert span == mock_span
        raise ValueError("Test exception")

# Verify exception was recorded and status set to error
mock_span.record_exception.assert_called_once()
mock_span.set_status.assert_called_once()
from pynector.telemetry import StatusCode
assert mock_span.set_status.call_args[0][0].status_code == StatusCode.ERROR
```

    assert isinstance(span, NoOpSpan)
    assert span.name == "test_span"
    assert span.attributes == {"key": "value"}

```
mock_span = MockSpan()
mock_token = "test_token"

# Mock the opentelemetry.context.detach function
detach_called = False
detach_token = None

def mock_detach(token):
    nonlocal detach_called, detach_token
    detach_called = True
    detach_token = token

# Patch the opentelemetry.context.detach import in AsyncSpanWrapper.__aexit__
with patch('pynector.telemetry.tracing.detach', mock_detach):
    wrapper = AsyncSpanWrapper(mock_span, mock_token)

    async with wrapper as span:
        assert span is mock_span
        assert mock_span.entered is True
        assert mock_span.exited is False

    assert mock_span.exited is True
    assert detach_called is True
    assert detach_token == mock_token
```

```
```
