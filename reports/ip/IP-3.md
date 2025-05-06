# Implementation Plan: Optional Observability

**Issue:** #3\
**Author:** pynector-implementer\
**Date:** 2025-05-05\
**Status:** Draft

## 1. Introduction

This Implementation Plan (IP) outlines the approach for implementing the
Optional Observability feature as specified in [TDS-3.md](../tds/TDS-3.md). The
implementation will provide a flexible, maintainable, and robust approach to
telemetry that makes OpenTelemetry tracing and structured logging optional
dependencies with no-op fallbacks, ensures proper context propagation across
async boundaries, and supports flexible configuration.

## 2. Project Structure

The Optional Observability feature will be implemented in the following
directory structure:

```
pynector/
├── telemetry/
│   ├── __init__.py           # Public API and factory functions
│   ├── config.py             # Configuration functions
│   ├── context.py            # Context propagation utilities
│   ├── facade.py             # Telemetry facade classes
│   ├── logging.py            # Logging implementations
│   └── tracing.py            # Tracing implementations
└── tests/
    └── telemetry/
        ├── __init__.py
        ├── test_config.py
        ├── test_context.py
        ├── test_facade.py
        ├── test_logging.py
        ├── test_tracing.py
        └── test_integration.py
```

## 3. Implementation Details

### 3.1 Dependency Detection (`__init__.py`)

```python
# Try to import OpenTelemetry
try:
    from opentelemetry import trace
    from opentelemetry.trace.status import Status, StatusCode
    HAS_OPENTELEMETRY = True
except ImportError:
    HAS_OPENTELEMETRY = False
    # Define status codes for no-op implementation
    class StatusCode:
        ERROR = 1
        OK = 0

    class Status:
        def __init__(self, status_code):
            self.status_code = status_code

# Try to import structlog
try:
    import structlog
    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False

# Public API
from pynector.telemetry.facade import TracingFacade, LoggingFacade
from pynector.telemetry.config import configure_telemetry

def get_telemetry(name: str) -> tuple[TracingFacade, LoggingFacade]:
    """Get tracer and logger instances for the given name.

    Args:
        name: The name to use for the tracer and logger

    Returns:
        A tuple containing a tracer and logger
    """
    return TracingFacade(name), LoggingFacade(name)
```

### 3.2 No-op Implementations (`tracing.py`)

```python
from typing import Dict, Any, Optional, ContextManager, AsyncContextManager
from contextlib import contextmanager, asynccontextmanager

class NoOpSpan:
    """No-op implementation of a span."""

    def __init__(self, name: str = "", attributes: Optional[Dict[str, Any]] = None):
        """Initialize a new no-op span.

        Args:
            name: The name of the span
            attributes: Optional attributes to set on the span
        """
        self.name = name
        self.attributes = attributes or {}

    def __enter__(self):
        """Enter the span context."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the span context."""
        pass

    async def __aenter__(self):
        """Enter the async span context."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async span context."""
        pass

    def set_attribute(self, key: str, value: Any) -> None:
        """Set an attribute on the span.

        Args:
            key: The attribute key
            value: The attribute value
        """
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to the span.

        Args:
            name: The event name
            attributes: Optional attributes for the event
        """
        pass

    def record_exception(self, exception: Exception) -> None:
        """Record an exception in the span.

        Args:
            exception: The exception to record
        """
        pass

    def set_status(self, status) -> None:
        """Set the status of the span.

        Args:
            status: The status to set
        """
        pass

class AsyncSpanWrapper:
    """Wrapper to make a regular span work as an async context manager."""

    def __init__(self, span, token=None):
        """Initialize a new async span wrapper.

        Args:
            span: The span to wrap
            token: Optional context token to detach when exiting
        """
        self.span = span
        self.token = token

    async def __aenter__(self):
        """Enter the async span context."""
        self.span.__enter__()
        return self.span

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async span context."""
        try:
            self.span.__exit__(exc_type, exc_val, exc_tb)
        finally:
            if self.token is not None:
                from opentelemetry.context import detach
                detach(self.token)
```

### 3.3 No-op Logger (`logging.py`)

```python
from typing import Dict, Any

class NoOpLogger:
    """No-op implementation of a logger."""

    def __init__(self, name: str = ""):
        """Initialize a new no-op logger.

        Args:
            name: The name of the logger
        """
        self.name = name

    def debug(self, event: str, **kwargs: Any) -> None:
        """Log a debug message (no-op).

        Args:
            event: The event name
            **kwargs: Additional key-value pairs to include in the log
        """
        pass

    def info(self, event: str, **kwargs: Any) -> None:
        """Log an info message (no-op).

        Args:
            event: The event name
            **kwargs: Additional key-value pairs to include in the log
        """
        pass

    def warning(self, event: str, **kwargs: Any) -> None:
        """Log a warning message (no-op).

        Args:
            event: The event name
            **kwargs: Additional key-value pairs to include in the log
        """
        pass

    def error(self, event: str, **kwargs: Any) -> None:
        """Log an error message (no-op).

        Args:
            event: The event name
            **kwargs: Additional key-value pairs to include in the log
        """
        pass

    def critical(self, event: str, **kwargs: Any) -> None:
        """Log a critical message (no-op).

        Args:
            event: The event name
            **kwargs: Additional key-value pairs to include in the log
        """
        pass
```

### 3.4 Telemetry Facades (`facade.py`)

```python
from typing import Dict, Any, Optional, ContextManager, AsyncContextManager
from pynector.telemetry import HAS_OPENTELEMETRY, HAS_STRUCTLOG, Status, StatusCode
from pynector.telemetry.tracing import NoOpSpan, AsyncSpanWrapper
from pynector.telemetry.logging import NoOpLogger

class TracingFacade:
    """Facade for tracing operations."""

    def __init__(self, name: str):
        """Initialize a new tracing facade.

        Args:
            name: The name of the tracer
        """
        self.name = name
        if HAS_OPENTELEMETRY:
            from opentelemetry import trace
            self.tracer = trace.get_tracer(name)
        else:
            self.tracer = None

    def start_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> ContextManager:
        """Start a new span.

        Args:
            name: The name of the span
            attributes: Optional attributes to set on the span

        Returns:
            A context manager that will end the span when exited
        """
        if HAS_OPENTELEMETRY and self.tracer:
            return self.tracer.start_span(name, attributes=attributes)
        return NoOpSpan(name, attributes)

    def start_as_current_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> ContextManager:
        """Start a new span and set it as the current span.

        Args:
            name: The name of the span
            attributes: Optional attributes to set on the span

        Returns:
            A context manager that will end the span when exited
        """
        if HAS_OPENTELEMETRY and self.tracer:
            return self.tracer.start_as_current_span(name, attributes=attributes)
        return NoOpSpan(name, attributes)

    async def start_async_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> AsyncContextManager:
        """Start a new span for async operations.

        Args:
            name: The name of the span
            attributes: Optional attributes to set on the span

        Returns:
            An async context manager that will end the span when exited
        """
        if HAS_OPENTELEMETRY and self.tracer:
            # Use a wrapper to make a regular span work as an async context manager
            span = self.tracer.start_span(name, attributes=attributes)
            return AsyncSpanWrapper(span)
        return NoOpSpan(name, attributes)

    async def start_as_current_async_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> AsyncContextManager:
        """Start a new span for async operations and set it as the current span.

        Args:
            name: The name of the span
            attributes: Optional attributes to set on the span

        Returns:
            An async context manager that will end the span when exited
        """
        if HAS_OPENTELEMETRY and self.tracer:
            # For async operations with OpenTelemetry, we need to ensure context propagation
            from opentelemetry.context import attach, detach, get_current

            # Capture current context
            token = attach(get_current())
            try:
                # Start a new span as the current span
                span = self.tracer.start_as_current_span(name, attributes=attributes)
                return AsyncSpanWrapper(span, token)
            except Exception:
                # If something goes wrong, detach the context
                detach(token)
                raise
        return NoOpSpan(name, attributes)

class LoggingFacade:
    """Facade for logging operations."""

    def __init__(self, name: str):
        """Initialize a new logging facade.

        Args:
            name: The name of the logger
        """
        self.name = name
        if HAS_STRUCTLOG:
            self.logger = structlog.get_logger(name)
        else:
            self.logger = NoOpLogger(name)

    def _add_trace_context(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Add trace context to log entries if available.

        Args:
            kwargs: The keyword arguments to add trace context to

        Returns:
            The updated keyword arguments
        """
        if HAS_OPENTELEMETRY:
            # Add trace context to logs
            from opentelemetry import trace
            current_span = trace.get_current_span()
            if current_span:
                context = current_span.get_span_context()
                if hasattr(context, 'is_valid') and context.is_valid:
                    kwargs["trace_id"] = format(context.trace_id, "032x")
                    kwargs["span_id"] = format(context.span_id, "016x")
        return kwargs

    def debug(self, event: str, **kwargs: Any) -> None:
        """Log a debug message.

        Args:
            event: The event name
            **kwargs: Additional key-value pairs to include in the log
        """
        kwargs = self._add_trace_context(kwargs)
        if HAS_STRUCTLOG:
            self.logger.debug(event, **kwargs)

    def info(self, event: str, **kwargs: Any) -> None:
        """Log an info message.

        Args:
            event: The event name
            **kwargs: Additional key-value pairs to include in the log
        """
        kwargs = self._add_trace_context(kwargs)
        if HAS_STRUCTLOG:
            self.logger.info(event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        """Log a warning message.

        Args:
            event: The event name
            **kwargs: Additional key-value pairs to include in the log
        """
        kwargs = self._add_trace_context(kwargs)
        if HAS_STRUCTLOG:
            self.logger.warning(event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        """Log an error message.

        Args:
            event: The event name
            **kwargs: Additional key-value pairs to include in the log
        """
        kwargs = self._add_trace_context(kwargs)
        if HAS_OPENTELEMETRY:
            # Mark span as error
            from opentelemetry import trace
            current_span = trace.get_current_span()
            if current_span:
                current_span.set_status(Status(StatusCode.ERROR))

        if HAS_STRUCTLOG:
            self.logger.error(event, **kwargs)

    def critical(self, event: str, **kwargs: Any) -> None:
        """Log a critical message.

        Args:
            event: The event name
            **kwargs: Additional key-value pairs to include in the log
        """
        kwargs = self._add_trace_context(kwargs)
        if HAS_OPENTELEMETRY:
            # Mark span as error
            from opentelemetry import trace
            current_span = trace.get_current_span()
            if current_span:
                current_span.set_status(Status(StatusCode.ERROR))

        if HAS_STRUCTLOG:
            self.logger.critical(event, **kwargs)
```

### 3.5 Context Propagation Utilities (`context.py`)

```python
import asyncio
from contextlib import asynccontextmanager
from typing import TypeVar, Callable, Awaitable, List, Any, Optional, Dict
from pynector.telemetry import HAS_OPENTELEMETRY, Status, StatusCode
from pynector.telemetry.facade import TracingFacade

T = TypeVar('T')

@asynccontextmanager
async def traced_async_operation(
    tracer: TracingFacade,
    name: str,
    attributes: Optional[Dict[str, Any]] = None
):
    """Context manager for tracing async operations.

    Args:
        tracer: The tracer to use
        name: The name of the span
        attributes: Optional attributes to set on the span

    Yields:
        The span
    """
    async with tracer.start_as_current_async_span(name, attributes=attributes) as span:
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR))
            raise

async def traced_gather(
    tracer: TracingFacade,
    coroutines: List[Awaitable[T]],
    name: str = "parallel_operations"
) -> List[T]:
    """Gather coroutines while preserving trace context.

    Args:
        tracer: The tracer to use
        coroutines: The coroutines to gather
        name: The name of the parent span

    Returns:
        The results of the coroutines
    """
    if not HAS_OPENTELEMETRY:
        # If OpenTelemetry is not available, just use regular gather
        return await asyncio.gather(*coroutines)

    # Start a parent span
    async with tracer.start_as_current_async_span(name) as span:
        # Capture current context with the active span
        from opentelemetry.context import attach, detach, get_current
        context = get_current()

        # Wrap each coroutine to propagate context
        async def with_context(coro):
            token = attach(context)
            try:
                return await coro
            finally:
                detach(token)

        # Run all coroutines with the same context
        wrapped = [with_context(coro) for coro in coroutines]
        return await asyncio.gather(*wrapped)

async def traced_task_group(
    tracer: TracingFacade,
    name: str,
    attributes: Optional[Dict[str, Any]] = None
):
    """Create a task group with trace context propagation.

    Args:
        tracer: The tracer to use
        name: The name of the parent span
        attributes: Optional attributes to set on the span

    Returns:
        A task group that propagates trace context
    """
    if not HAS_OPENTELEMETRY:
        # If OpenTelemetry is not available, just use regular task group
        from anyio import create_task_group
        return await create_task_group()

    # Start a parent span
    async with tracer.start_as_current_async_span(name, attributes=attributes) as span:
        # Capture current context with the active span
        from opentelemetry.context import attach, detach, get_current
        from anyio import create_task_group

        context = get_current()
        task_group = await create_task_group()

        # Wrap the start_soon method to propagate context
        original_start_soon = task_group.start_soon

        async def start_soon_with_context(func, *args, **kwargs):
            async def wrapped_func(*args, **kwargs):
                token = attach(context)
                try:
                    return await func(*args, **kwargs)
                finally:
                    detach(token)

            await original_start_soon(wrapped_func, *args, **kwargs)

        task_group.start_soon = start_soon_with_context
        return task_group
```

### 3.6 Configuration (`config.py`)

```python
import os
from typing import Dict, Any, Optional, List
from pynector.telemetry import HAS_OPENTELEMETRY, HAS_STRUCTLOG

def get_env_bool(name: str, default: bool = False) -> bool:
    """Get a boolean value from an environment variable.

    Args:
        name: The name of the environment variable
        default: The default value if the environment variable is not set

    Returns:
        The boolean value
    """
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "y", "t")

def get_env_dict(name: str, default: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Get a dictionary from a comma-separated environment variable.

    Args:
        name: The name of the environment variable
        default: The default value if the environment variable is not set

    Returns:
        The dictionary
    """
    value = os.environ.get(name)
    if not value:
        return default or {}

    result = {}
    for pair in value.split(","):
        if "=" in pair:
            key, val = pair.split("=", 1)
            result[key.strip()] = val.strip()
    return result

def configure_telemetry(
    service_name: Optional[str] = None,
    resource_attributes: Optional[Dict[str, str]] = None,
    trace_enabled: Optional[bool] = None,
    log_level: str = "INFO",
    log_processors: Optional[List[Any]] = None,
    trace_exporters: Optional[List[str]] = None,
) -> bool:
    """Configure OpenTelemetry and structlog with sensible defaults.

    Args:
        service_name: The name of the service
        resource_attributes: Additional resource attributes
        trace_enabled: Whether tracing is enabled
        log_level: The log level
        log_processors: Additional log processors
        trace_exporters: The trace exporters to use

    Returns:
        True if tracing is enabled, False otherwise
    """
    # Check if dependencies are available
    if not (HAS_OPENTELEMETRY or HAS_STRUCTLOG):
        return False

    # Determine if tracing is enabled
    if trace_enabled is None:
        trace_enabled = not get_env_bool("OTEL_SDK_DISABLED", False)

    # Get service name
    if service_name is None:
        service_name = os.environ.get("OTEL_SERVICE_NAME", "unknown_service")

    # Get resource attributes
    if resource_attributes is None:
        resource_attributes = {}

    env_attrs = get_env_dict("OTEL_RESOURCE_ATTRIBUTES")
    resource_attributes = {**env_attrs, **resource_attributes}

    # Ensure service name is in resource attributes
    resource_attributes["service.name"] = service_name

    # Configure OpenTelemetry if enabled and available
    if trace_enabled and HAS_OPENTELEMETRY:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.resources import Resource

        # Create resource with service info
        resource = Resource.create(resource_attributes)

        # Create and set tracer provider
        tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(tracer_provider)

        # Configure exporters
        _configure_exporters(tracer_provider, trace_exporters)

    # Configure structlog if available
    if HAS_STRUCTLOG:
        _configure_structlog(log_level, log_processors)

    return trace_enabled

def _configure_exporters(tracer_provider, exporters=None):
    """Configure trace exporters.

    Args:
        tracer_provider: The tracer provider to configure
        exporters: The exporters to use, or None to use the default
    """
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    # Determine which exporters to use
    if exporters is None:
        exporter_env = os.environ.get("OTEL_TRACES_EXPORTER", "otlp")
        exporters = [ex.strip() for ex in exporter_env.split(",")]

    # Configure each exporter
    for exporter_name in exporters:
        if exporter_name == "otlp":
            # OTLP exporter
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
            if otlp_endpoint:
                exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            else:
                exporter = OTLPSpanExporter()
            tracer_provider.add_span_processor(BatchSpanProcessor(exporter))

        elif exporter_name == "console":
            # Console exporter
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter
            tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

        elif exporter_name == "zipkin":
            # Zipkin exporter
            from opentelemetry.exporter.zipkin.json import ZipkinExporter
            zipkin_endpoint = os.environ.get("OTEL_EXPORTER_ZIPKIN_ENDPOINT")
            if zipkin_endpoint:
                exporter = ZipkinExporter(endpoint=zipkin_endpoint)
            else:
                exporter = ZipkinExporter()
            tracer_provider.add_span_processor(BatchSpanProcessor(exporter))

def _configure_structlog(log_level, processors=None):
    """Configure structlog.

    Args:
        log_level: The log level
        processors: Additional processors to add
    """
    import structlog
    import logging

    # Set up logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level),
    )

    # Define custom processor to add trace context
    def add_trace_context(_, __, event_dict):
        """Add trace context to log entries if available."""
        if HAS_OPENTELEMETRY:
            from opentelemetry import trace
            current_span = trace.get_current_span()
            if current_span:
                context = current_span.get_span_context()
                if hasattr(context, 'is_valid') and context.is_valid:
                    event_dict["trace_id"] = format(context.trace_id, "032x")
                    event_dict["span_id"] = format(context.span_id, "016x")
        return event_dict

    # Define processors
    default_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        add_trace_context,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]

    # Add custom processors
    if processors:
        default_processors.extend(processors)

    # Configure structlog
    structlog.configure(
        processors=default_processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
```

## 4. Implementation Approach

The implementation will follow these steps:

1. **Set up project structure:** Create the necessary directories and files
2. **Implement dependency detection:** Implement the code to detect optional
   dependencies
3. **Implement no-op fallbacks:** Implement the no-op implementations for when
   dependencies are missing
4. **Implement telemetry facades:** Implement the facade classes for tracing and
   logging
5. **Implement context propagation:** Implement the utilities for context
   propagation in async code
6. **Implement configuration:** Implement the configuration functions
7. **Write tests:** Write comprehensive tests for all components
8. **Documentation:** Add docstrings and type hints to all components

## 5. Dependencies

The implementation will require the following dependencies:

- Python 3.9 or higher (as specified in pyproject.toml)
- Standard library modules:
  - `typing` for type hints
  - `contextlib` for context managers
  - `os` for environment variables
  - `asyncio` for async/await support

Optional dependencies (declared in pyproject.toml):

- `opentelemetry-api>=1.18.0`
- `opentelemetry-sdk>=1.18.0`
- `structlog>=23.1.0`
- `opentelemetry-exporter-otlp>=1.18.0` (optional)
- `opentelemetry-exporter-zipkin>=1.18.0` (optional)

## 6. Testing Strategy

The testing strategy is detailed in the Test Implementation document (TI-3.md).
It will include:

- Unit tests for all components
- Integration tests for component interactions
- Tests with and without optional dependencies
- Tests for context propagation in async code
- Tests for configuration options

## 7. References

1. Technical Design Specification: Optional Observability (TDS-3.md) (search:
   internal-document)
2. Research Report: OpenTelemetry Tracing and Structured Logging in Async Python
   Libraries (RR-3.md) (search: internal-document)
3. OpenTelemetry Python Documentation (search:
   exa-opentelemetry-python.readthedocs.io)
4. OpenTelemetry Context Propagation (search:
   exa-opentelemetry.io/docs/concepts/context-propagation/)
5. OpenTelemetry Environment Variable Specification (search:
   exa-opentelemetry.io/docs/specs/otel/configuration/sdk-environment-variables/)
6. Structlog Documentation (search: exa-www.structlog.org/en/stable/)
7. Python Optional Dependencies (search:
   exa-github.com/kevinsawade/optional_imports)
