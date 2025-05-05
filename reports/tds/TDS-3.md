# Technical Design Specification: Optional Observability

**Issue:** #3\
**Author:** pynector-architect\
**Date:** 2025-05-05\
**Status:** Draft

## 1. Introduction

This Technical Design Specification (TDS) defines the architecture and
implementation details for Optional Observability in the pynector project. The
design is based on the research findings documented in [RR-3.md](../rr/RR-3.md)
and additional research.

### 1.1 Purpose

The Optional Observability implementation provides a flexible, maintainable, and
robust approach to telemetry that:

- Makes OpenTelemetry tracing and structured logging (e.g., structlog) optional
  dependencies
- Provides no-op fallbacks when dependencies are not available
- Ensures proper context propagation across async boundaries
- Supports flexible configuration via environment variables and programmatic
  APIs
- Integrates tracing and logging for comprehensive observability

### 1.2 Scope

This specification covers:

- The Telemetry Facade design for abstracting OpenTelemetry and structlog
- No-op fallback implementations for optional dependencies
- Context propagation strategies for async code
- Configuration options and defaults
- Integration patterns for the rest of the library

### 1.3 Design Principles

The design adheres to the following principles:

1. **Optional Dependencies:** Telemetry features should be optional and not
   required for core functionality
2. **Graceful Degradation:** The library should work correctly even when
   dependencies are missing
3. **Consistent API:** The API should remain consistent regardless of whether
   dependencies are available
4. **Context Preservation:** Trace context should be properly propagated across
   async boundaries
5. **Configuration Flexibility:** Support both environment variables and
   programmatic configuration

## 2. Architecture Overview

The Optional Observability implementation consists of the following components:

1. **Telemetry Facade:** Abstracts away the details of OpenTelemetry and
   structlog
2. **No-op Implementations:** Provide fallbacks when dependencies are missing
3. **Context Propagation:** Ensures trace context is maintained across async
   boundaries
4. **Configuration:** Provides flexible configuration options

### 2.1 Component Diagram

```
┌─────────────────────────────────────┐
│           Client Application        │
└───────────────┬─────────────────────┘
                │
                ▼
┌─────────────────────────────────────┐
│         Telemetry Facade            │
├─────────────────────────────────────┤
│  - TracingFacade                    │
│  - LoggingFacade                    │
│  - get_telemetry()                  │
└───────────────┬─────────────────────┘
                │ uses
                ▼
┌─────────────────────────────────────┐
│       Dependency Detection          │
├─────────────────────────────────────┤
│  - HAS_OPENTELEMETRY                │
│  - HAS_STRUCTLOG                    │
└───────────────┬─────────────────────┘
                │ creates
                ▼
┌───────────────┴─────────────────────┐
│                                     │
│  ┌─────────────┐    ┌─────────────┐ │
│  │ Real Impl   │    │  No-op Impl │ │
│  │ (if avail.) │    │ (fallback)  │ │
│  └─────────────┘    └─────────────┘ │
│                                     │
└─────────────────────────────────────┘
```

## 3. Telemetry Facade

The Telemetry Facade provides a unified interface for tracing and logging,
abstracting away the details of the underlying implementations.

### 3.1 TracingFacade Interface

```python
from typing import Optional, Dict, Any, ContextManager, AsyncContextManager

class TracingFacade:
    """Facade for tracing operations."""
    
    def __init__(self, name: str):
        """Initialize a new tracing facade.
        
        Args:
            name: The name of the tracer
        """
        ...
        
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
        ...
        
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
        ...
        
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
        ...
        
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
        ...
```

### 3.2 LoggingFacade Interface

```python
from typing import Dict, Any, Optional

class LoggingFacade:
    """Facade for logging operations."""
    
    def __init__(self, name: str):
        """Initialize a new logging facade.
        
        Args:
            name: The name of the logger
        """
        ...
        
    def debug(self, event: str, **kwargs: Any) -> None:
        """Log a debug message.
        
        Args:
            event: The event name
            **kwargs: Additional key-value pairs to include in the log
        """
        ...
        
    def info(self, event: str, **kwargs: Any) -> None:
        """Log an info message.
        
        Args:
            event: The event name
            **kwargs: Additional key-value pairs to include in the log
        """
        ...
        
    def warning(self, event: str, **kwargs: Any) -> None:
        """Log a warning message.
        
        Args:
            event: The event name
            **kwargs: Additional key-value pairs to include in the log
        """
        ...
        
    def error(self, event: str, **kwargs: Any) -> None:
        """Log an error message.
        
        Args:
            event: The event name
            **kwargs: Additional key-value pairs to include in the log
        """
        ...
        
    def critical(self, event: str, **kwargs: Any) -> None:
        """Log a critical message.
        
        Args:
            event: The event name
            **kwargs: Additional key-value pairs to include in the log
        """
        ...
```

### 3.3 Factory Function

```python
def get_telemetry(name: str) -> tuple[TracingFacade, LoggingFacade]:
    """Get tracer and logger instances for the given name.
    
    Args:
        name: The name to use for the tracer and logger
        
    Returns:
        A tuple containing a tracer and logger
    """
    return TracingFacade(name), LoggingFacade(name)
```

### 3.4 Usage Example

```python
from pynector.telemetry import get_telemetry

# Get tracer and logger
tracer, logger = get_telemetry("pynector.module")

def process_data(data):
    # Log with structured data
    logger.info("processing_data", data_size=len(data))
    
    # Create a span for the operation
    with tracer.start_as_current_span("process_data", attributes={"data_size": len(data)}) as span:
        try:
            result = perform_processing(data)
            span.set_attribute("result_size", len(result))
            logger.info("processing_complete", result_size=len(result))
            return result
        except Exception as e:
            # Record exception in span and log
            span.record_exception(e)
            logger.error("processing_failed", error=str(e))
            raise

async def process_data_async(data):
    # Log with structured data
    logger.info("processing_data_async", data_size=len(data))
    
    # Create a span for the async operation
    async with tracer.start_as_current_async_span("process_data_async", attributes={"data_size": len(data)}) as span:
        try:
            result = await perform_processing_async(data)
            span.set_attribute("result_size", len(result))
            logger.info("processing_complete", result_size=len(result))
            return result
        except Exception as e:
            # Record exception in span and log
            span.record_exception(e)
            logger.error("processing_failed", error=str(e))
            raise
```

## 4. No-op Implementations

No-op implementations provide fallbacks when dependencies are not available,
ensuring that the library works correctly even without the optional
dependencies.

### 4.1 Dependency Detection

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
```

### 4.2 No-op Span Implementation

```python
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
        
    def set_status(self, status: Status) -> None:
        """Set the status of the span.
        
        Args:
            status: The status to set
        """
        pass
```

### 4.3 No-op Logger Implementation

```python
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

### 4.4 Facade Implementations with Fallbacks

```python
class TracingFacade:
    """Facade for tracing operations."""
    
    def __init__(self, name: str):
        """Initialize a new tracing facade.
        
        Args:
            name: The name of the tracer
        """
        self.name = name
        if HAS_OPENTELEMETRY:
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
            current_span = trace.get_current_span()
            if current_span:
                current_span.set_status(Status(StatusCode.ERROR))
                
        if HAS_STRUCTLOG:
            self.logger.critical(event, **kwargs)
```

### 4.5 Async Span Wrapper

```python
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

## 5. Context Propagation

Context propagation ensures that trace context is properly maintained across
async boundaries, allowing for accurate tracing of asynchronous operations.

### 5.1 Async Context Propagation

```python
import asyncio
from contextlib import asynccontextmanager
from typing import TypeVar, Callable, Awaitable, List, Any, Optional

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
```

### 5.2 Task Group Integration

```python
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

### 5.3 Usage Example

```python
async def process_items(items, tracer, logger):
    """Process multiple items in parallel with trace context propagation."""
    async with traced_async_operation(tracer, "process_items", {"item_count": len(items)}) as span:
        logger.info("processing_items", item_count=len(items))
        
        # Process items in parallel with trace context propagation
        results = await traced_gather(
            tracer,
            [process_item(item, tracer, logger) for item in items],
            "process_items_parallel"
        )
        
        span.set_attribute("processed_count", len(results))
        logger.info("items_processed", processed_count=len(results))
        return results

async def process_item(item, tracer, logger):
    """Process a single item with tracing."""
    async with traced_async_operation(tracer, "process_item", {"item_id": item.id}) as span:
        logger.info("processing_item", item_id=item.id)
        
        # Simulate processing
        await asyncio.sleep(0.1)
        
        result = {"id": item.id, "processed": True}
        span.set_attribute("result", str(result))
        logger.info("item_processed", item_id=item.id, result=result)
        return result
```

## 6. Configuration

The configuration system provides flexible options for configuring OpenTelemetry
and structlog, supporting both environment variables and programmatic
configuration.

### 6.1 Environment Variables

```python
import os
from typing import Dict, Any, Optional

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
```

### 6.2 Configuration Function

```python
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

### 6.3 Usage Example

```python
from pynector.telemetry import configure_telemetry, get_telemetry

# Configure telemetry with environment variables
trace_enabled = configure_telemetry()

# Or configure programmatically
trace_enabled = configure_telemetry(
    service_name="my-service",
    resource_attributes={"deployment.environment": "production"},
    trace_enabled=True,
    log_level="INFO",
    trace_exporters=["console"],
)

# Get tracer and logger
tracer, logger = get_telemetry("my-module")
```

## 7. Implementation Considerations

### 7.1 Optional Dependencies in pyproject.toml

The optional dependencies should be declared in the project's `pyproject.toml`
file:

```toml
[project]
# Project metadata
name = "pynector"
version = "0.1.0"
# ...

# Dependencies
dependencies = [
    # Core dependencies
]

[project.optional-dependencies]
# Optional observability dependencies
observability = [
    "opentelemetry-api>=1.18.0",
    "opentelemetry-sdk>=1.18.0",
    "structlog>=23.1.0",
]

# Additional exporters
otlp = [
    "opentelemetry-exporter-otlp>=1.18.0",
]

zipkin = [
    "opentelemetry-exporter-zipkin>=1.18.0",
]

# Full observability stack
observability-full = [
    "pynector[observability,otlp,zipkin]",
]
```

### 7.2 Import Considerations

When importing the telemetry module, care should be taken to avoid unnecessary
imports:

```python
# Good: Import only what's needed
from pynector.telemetry import get_telemetry

# Good: Only configure when needed
from pynector.telemetry import configure_telemetry

# Avoid: This might import OpenTelemetry even if it's not used
from pynector.telemetry import TracingFacade
```

### 7.3 Thread Safety

The telemetry implementation should be thread-safe to ensure correct behavior in
multi-threaded environments:

1. **Lazy Initialization**: Initialize resources only when needed
2. **Thread-Local Storage**: Use thread-local storage or context vars for
   per-thread state
3. **Immutable State**: Keep shared state immutable where possible

### 7.4 Performance Considerations

To minimize the performance impact of telemetry:

1. **No-op Fast Path**: Make the no-op path as fast as possible
2. **Batch Processing**: Use batch span processors for efficient exporting
3. **Sampling**: Use appropriate sampling strategies based on load
4. **Lazy Evaluation**: Avoid expensive computations for logs that might be
   filtered out

## 8. Future Considerations

The following areas are identified for future expansion:

1. **Additional Exporters**: Support for additional OpenTelemetry exporters
   (e.g., Prometheus, Jaeger)
2. **Metrics Support**: Extend the telemetry facade to support OpenTelemetry
   metrics
3. **Distributed Tracing**: Enhanced support for distributed tracing with
   context propagation across services
4. **Custom Instrumentations**: Pre-built instrumentations for common libraries
   (e.g., HTTP clients, databases)
5. **Semantic Conventions**: Better support for OpenTelemetry semantic
   conventions
6. **Sampling Strategies**: More sophisticated sampling strategies for
   high-throughput applications

## 9. References

1. Research Report: OpenTelemetry Tracing and Structured Logging in Async Python
   Libraries (RR-3.md) (search: internal-document)
2. OpenTelemetry Python Documentation (search:
   exa-opentelemetry-python.readthedocs.io)
3. OpenTelemetry Context Propagation (search:
   exa-opentelemetry.io/docs/concepts/context-propagation/)
4. OpenTelemetry Environment Variable Specification (search:
   exa-opentelemetry.io/docs/specs/otel/configuration/sdk-environment-variables/)
5. Structlog Documentation (search: exa-www.structlog.org/en/stable/)
6. Sans-I/O Python Libraries (search: exa-sans-io.readthedocs.io)
7. AnyIO Documentation (search: exa-anyio.readthedocs.io)
8. Python Optional Dependencies (search:
   exa-github.com/kevinsawade/optional_imports)
