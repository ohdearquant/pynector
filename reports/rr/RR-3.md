# Research Report: OpenTelemetry Tracing and Structured Logging in Async Python Libraries

**Issue:** #3\
**Author:** pynector-researcher\
**Date:** 2025-05-05\
**Status:** Complete

## 1. Executive Summary

This research report explores best practices and implementation patterns for
integrating OpenTelemetry tracing and structured logging (e.g., `structlog`) in
an async Python library. The focus areas are no-op fallbacks for optional
dependencies, context propagation across async boundaries, and configuration
options.

Key findings:

- Several patterns exist for implementing optional dependencies with no-op
  fallbacks, ranging from simple function replacements to sophisticated wrapper
  classes
- Context propagation in async code requires special handling, with
  OpenTelemetry providing both automatic and manual approaches
- OpenTelemetry offers extensive configuration options via environment
  variables, allowing for flexible deployment
- While structlog is a powerful structured logging library, direct integration
  with OpenTelemetry requires custom implementation

## 2. No-op Fallbacks for Optional Dependencies

### 2.1 The Challenge of Optional Dependencies

Python libraries often need to support optional dependencies to:

- Reduce installation footprint
- Avoid unnecessary dependencies for users who don't need certain features
- Allow flexibility in choosing compatible versions of dependencies

However, this creates a challenge: how to handle the case when an optional
dependency is not available without causing import errors or requiring complex
conditional code throughout the codebase.

### 2.2 Implementation Patterns

#### 2.2.1 Simple Function Replacement

The simplest approach is to replace functions from missing modules with no-op
functions:

```python
def noop_module(module):
    for thing in module.__dir__():
        if inspect.isclass(getattr(module, thing)):
            # set classes to object in case of inheritance
            setattr(module, thing, object)
        else:
            setattr(module, thing, lambda *args, **kwargs: None)
```

**Source:** [python-noop](https://github.com/joshp123/python-noop) (search:
exa-github.com/joshp123/python-noop)

This approach is simple but aggressive, completely replacing the module's
functionality with no-ops.

#### 2.2.2 Fallback Wrapper Class

A more sophisticated approach is to use a wrapper class that provides fallbacks
when operations on the wrapped object fail:

```python
class Fallback:
    def __init__(self, obj: any = None, fallback: any = None):
        self._obj = obj
        self._fallback = fallback

    def __getattr__(self, item):
        if self._obj is None:
            return Fallback(fallback=self._fallback)
        try:
            return Fallback(obj=getattr(self._obj, item), fallback=self._fallback)
        except (KeyError, AttributeError):
            return Fallback(fallback=self._fallback)

    def __call__(self, *args, **kwargs) -> Fallback:
        try:
            return Fallback(obj=self._obj(*args, **kwargs), fallback=self._fallback)
        except TypeError:
            return Fallback(fallback=self._fallback)
```

**Source:** [pyfallback](https://github.com/weilueluo/pyfallback) (search:
exa-github.com/weilueluo/pyfallback)

This approach maintains the fallback chain and handles various operations like
attribute access, item access, iteration, and calling.

#### 2.2.3 Optional Import Function

A more targeted approach is to use a function specifically designed for optional
imports:

```python
def _optional_import(
    module: str,
    name: str = None,
    version: str = None,
    auto_install: bool = False,
    user_install: bool = False,
) -> Any:
    """Function that allows optional imports."""
    import importlib
    _module = module
    try:
        module = importlib.import_module(module)
        if name is None:
            return module
        if '.' in name:
            for i in name.split('.'):
                module = getattr(module, i)
            return module
        return getattr(module, name)
    except ImportError as e:
        # import failed
        if version is not None:
            msg = f"Install the `{_module}` package with version `{version}` to make use of this feature."
        else:
            msg = f"Install the `{_module}` package to make use of this feature."
        import_error = e

    # failed import class closure
    class _failed_import:
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, *args, **kwargs):
            raise ValueError(msg) from import_error

        def __getattribute__(self, name):
            # if class is base class for some other class
            if name == '__mro_entries__':
                return object.__getattribute__(self, name)
            raise ValueError(msg) from import_error

    return _failed_import()
```

**Source:** [optional_imports](https://github.com/kevinsawade/optional_imports)
(search: exa-github.com/kevinsawade/optional_imports)

This approach provides detailed error messages and handles inheritance, making
it suitable for more complex scenarios.

### 2.3 Recommended Pattern for OpenTelemetry

For OpenTelemetry integration, a hybrid approach is recommended:

```python
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.resources import Resource
    HAS_OPENTELEMETRY = True
except ImportError:
    HAS_OPENTELEMETRY = False

    # Create no-op implementations
    class NoOpSpan:
        def __enter__(self): return self
        def __exit__(self, exc_type, exc_val, exc_tb): pass
        def set_attribute(self, key, value): pass
        def add_event(self, name, attributes=None): pass
        def record_exception(self, exception): pass

    class NoOpTracer:
        def start_span(self, name, context=None, kind=None, attributes=None):
            return NoOpSpan()
        def start_as_current_span(self, name, context=None, kind=None, attributes=None):
            return NoOpSpan()

    class NoOpTracerProvider:
        def get_tracer(self, name, version=None):
            return NoOpTracer()

    # Create module-level functions and objects
    def get_tracer(name, version=None):
        return NoOpTracer()

    def get_current_span():
        return NoOpSpan()

    trace = type('trace', (), {
        'get_tracer': get_tracer,
        'get_current_span': get_current_span,
    })
```

This approach:

- Checks for OpenTelemetry availability
- Provides no-op implementations that match the OpenTelemetry API
- Allows code to use OpenTelemetry without conditional checks throughout

## 3. Context Propagation Across Async Boundaries

### 3.1 The Challenge of Async Context

In asynchronous code, context can be lost when:

- Switching between coroutines
- Using multiple event loops
- Using thread pools or process pools

This is particularly challenging for distributed tracing, where context needs to
be maintained across these boundaries to properly track the flow of execution.

### 3.2 OpenTelemetry Context Propagation

OpenTelemetry provides several mechanisms for context propagation in async code:

#### 3.2.1 Using `trace.use_span()`

The simplest approach is to use `trace.use_span()` to maintain context in async
functions:

```python
import asyncio
from opentelemetry import baggage, trace
from opentelemetry.sdk.trace import TracerProvider

trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

async def async_span(span):
    with trace.use_span(span):
        ctx = baggage.set_baggage("foo", "bar")
    return ctx

async def main():
    span = tracer.start_span(name="span")
    ctx = await async_span(span)
    print(baggage.get_all(context=ctx))
```

**Source:**
[OpenTelemetry Python async_context.py](https://raw.githubusercontent.com/open-telemetry/opentelemetry-python/main/docs/examples/basic_context/async_context.py)
(search:
exa-opentelemetry-python.readthedocs.io/en/stable/examples/basic_context/README.html)

This approach works well for simple async scenarios where the context is passed
explicitly.

#### 3.2.2 Manual Context Propagation

For more complex scenarios, context can be manually captured and attached:

```python
import asyncio
from opentelemetry.context import attach, detach, get_current

async def worker(context, question):
    # Attach the captured context to this task
    token = attach(context)
    try:
        # Work happens here, with the context from the main thread
        # Any spans created here will be children of the parent span
        return process_question(question)
    finally:
        # Always detach the context when done
        detach(token)

async def process_questions(questions):
    # Capture the current context (including any active spans)
    context = get_current()

    # Create tasks with the captured context
    tasks = [asyncio.create_task(worker(context, q)) for q in questions]
    return await asyncio.gather(*tasks)
```

**Source:**
[Advanced Tracing (OTEL) Examples](https://docs.arize.com/arize/llm-tracing/how-to-tracing-manual/advanced-tracing-otel-examples)
(search:
exa-docs.arize.com/arize/llm-tracing/how-to-tracing-manual/advanced-tracing-otel-examples)

This approach gives more control over context propagation and is useful for
complex async workflows.

### 3.3 Recommended Pattern for Async Libraries

For async libraries, a combination of automatic and manual context propagation
is recommended:

```python
import asyncio
from contextlib import asynccontextmanager
from opentelemetry import trace
from opentelemetry.context import attach, detach, get_current

# For simple cases, use async context managers
@asynccontextmanager
async def traced_async_operation(name, attributes=None):
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span(name, attributes=attributes) as span:
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            raise

# For complex cases with multiple tasks, use manual context propagation
async def traced_gather(coroutines, name="parallel_operations"):
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span(name) as span:
        # Capture current context with the active span
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

This approach provides both convenience for simple cases and flexibility for
complex scenarios.

## 4. Configuration Options

### 4.1 OpenTelemetry Configuration

OpenTelemetry provides extensive configuration options via environment
variables, allowing for flexible deployment without code changes.

#### 4.1.1 Core Environment Variables

| Name                     | Description                                             | Default                 |
| ------------------------ | ------------------------------------------------------- | ----------------------- |
| OTEL_SDK_DISABLED        | Disable the SDK for all signals                         | false                   |
| OTEL_RESOURCE_ATTRIBUTES | Key-value pairs for resource attributes                 | Empty                   |
| OTEL_SERVICE_NAME        | Sets the value of the `service.name` resource attribute | "unknown_service"       |
| OTEL_PROPAGATORS         | Propagators to be used as a comma-separated list        | "tracecontext,baggage"  |
| OTEL_TRACES_SAMPLER      | Sampler to be used for traces                           | "parentbased_always_on" |
| OTEL_TRACES_EXPORTER     | Specifies which exporter is used for traces             | "otlp"                  |

**Source:**
[OpenTelemetry Environment Variable Specification](https://opentelemetry.io/docs/specs/otel/configuration/sdk-environment-variables/)
(search:
exa-opentelemetry.io/docs/specs/otel/configuration/sdk-environment-variables/)

#### 4.1.2 Programmatic Configuration

In addition to environment variables, OpenTelemetry can be configured
programmatically:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# Configure resource with service info
resource = Resource.create({
    "service.name": "my-service",
    "service.version": "1.0.0",
    "deployment.environment": "production"
})

# Create and set tracer provider
tracer_provider = TracerProvider(resource=resource)
trace.set_tracer_provider(tracer_provider)

# Add span processor with exporter
tracer_provider.add_span_processor(
    BatchSpanProcessor(ConsoleSpanExporter())
)
```

**Source:**
[OpenTelemetry Python SDK](https://opentelemetry-python.readthedocs.io/en/latest/sdk/index.html)
(search: exa-opentelemetry-python.readthedocs.io/en/latest/sdk/index.html)

### 4.2 Structlog Configuration

Structlog provides its own configuration options that need to be integrated with
OpenTelemetry:

```python
import structlog
from opentelemetry import trace

# Configure structlog
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.PrintLoggerFactory(),
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    cache_logger_on_first_use=True,
)

# Add OpenTelemetry trace context to structlog
def add_trace_context(_, __, event_dict):
    current_span = trace.get_current_span()
    if current_span:
        context = current_span.get_span_context()
        if context.is_valid:
            event_dict["trace_id"] = format(context.trace_id, "032x")
            event_dict["span_id"] = format(context.span_id, "016x")
    return event_dict

# Update structlog processors
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        add_trace_context,  # Add OpenTelemetry context
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.PrintLoggerFactory(),
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    cache_logger_on_first_use=True,
)
```

**Source:** Based on structlog documentation (search:
exa-www.structlog.org/en/stable/)

### 4.3 Recommended Configuration Pattern

For a library that integrates OpenTelemetry and structlog, a flexible
configuration approach is recommended:

```python
import os
import structlog
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource

def configure_telemetry(
    service_name=None,
    resource_attributes=None,
    trace_enabled=None,
    log_level="INFO",
):
    """Configure OpenTelemetry and structlog with sensible defaults."""
    # Determine if tracing is enabled
    if trace_enabled is None:
        trace_enabled = os.environ.get("OTEL_SDK_DISABLED", "false").lower() != "true"

    # Get service name
    if service_name is None:
        service_name = os.environ.get("OTEL_SERVICE_NAME", "unknown_service")

    # Get resource attributes
    if resource_attributes is None:
        resource_attributes = {}
        env_attrs = os.environ.get("OTEL_RESOURCE_ATTRIBUTES", "")
        if env_attrs:
            for pair in env_attrs.split(","):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    resource_attributes[key.strip()] = value.strip()

    # Ensure service name is in resource attributes
    resource_attributes["service.name"] = service_name

    # Configure OpenTelemetry if enabled
    if trace_enabled:
        resource = Resource.create(resource_attributes)
        tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(tracer_provider)

        # Configure exporters based on environment variables
        configure_exporters(tracer_provider)

    # Configure structlog
    configure_structlog(log_level, trace_enabled)

    return trace_enabled
```

This approach:

- Respects environment variables for configuration
- Allows programmatic overrides
- Integrates OpenTelemetry and structlog configuration
- Provides sensible defaults

## 5. Integration Patterns

### 5.1 Library Design Considerations

When designing a library that integrates OpenTelemetry and structlog, several
considerations are important:

1. **Optional Dependencies**: Make both OpenTelemetry and structlog optional
   dependencies
2. **No-op Fallbacks**: Provide no-op implementations when dependencies are
   missing
3. **Context Propagation**: Ensure context is properly propagated in async code
4. **Configuration**: Support both environment variables and programmatic
   configuration
5. **API Stability**: Provide a stable API regardless of whether dependencies
   are available

### 5.2 Integration Architecture

A recommended architecture for integrating OpenTelemetry and structlog:

```
┌─────────────────────────────────────────┐
│             Library Public API          │
└───────────────────┬─────────────────────┘
                    │
┌───────────────────┴─────────────────────┐
│         Instrumentation Layer           │
│  ┌─────────────┐        ┌─────────────┐ │
│  │  Tracing    │        │  Logging    │ │
│  │  Facade     │        │  Facade     │ │
│  └──────┬──────┘        └──────┬──────┘ │
└─────────┼─────────────────────┼─────────┘
          │                     │
┌─────────┴─────────┐ ┌─────────┴─────────┐
│   OpenTelemetry   │ │     structlog     │
│   (if available)  │ │  (if available)   │
└───────────────────┘ └───────────────────┘
```

This architecture:

- Separates the public API from the implementation details
- Uses facade patterns to abstract away the dependencies
- Allows for graceful degradation when dependencies are missing

### 5.3 Implementation Example

A simplified implementation of this architecture:

```python
# telemetry.py - Facade module for telemetry

# Try to import dependencies
try:
    import structlog
    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False

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

# Tracing facade
class TracingFacade:
    def __init__(self, name):
        self.name = name
        if HAS_OPENTELEMETRY:
            self.tracer = trace.get_tracer(name)
        else:
            self.tracer = None

    def start_span(self, name, attributes=None):
        if self.tracer:
            return self.tracer.start_span(name, attributes=attributes)
        return NoOpSpan()

    def start_as_current_span(self, name, attributes=None):
        if self.tracer:
            return self.tracer.start_as_current_span(name, attributes=attributes)
        return NoOpSpan()

# Logging facade
class LoggingFacade:
    def __init__(self, name):
        self.name = name
        if HAS_STRUCTLOG:
            self.logger = structlog.get_logger(name)
        else:
            self.logger = NoOpLogger()

    def info(self, event, **kwargs):
        if HAS_OPENTELEMETRY:
            # Add trace context to logs
            current_span = trace.get_current_span()
            if current_span:
                context = current_span.get_span_context()
                if context.is_valid:
                    kwargs["trace_id"] = format(context.trace_id, "032x")
                    kwargs["span_id"] = format(context.span_id, "016x")
        return self.logger.info(event, **kwargs)

    def error(self, event, **kwargs):
        if HAS_OPENTELEMETRY:
            # Add trace context to logs
            current_span = trace.get_current_span()
            if current_span:
                context = current_span.get_span_context()
                if context.is_valid:
                    kwargs["trace_id"] = format(context.trace_id, "032x")
                    kwargs["span_id"] = format(context.span_id, "016x")
                    # Mark span as error
                    current_span.set_status(Status(StatusCode.ERROR))
        return self.logger.error(event, **kwargs)

# No-op implementations
class NoOpSpan:
    def __enter__(self): return self
    def __exit__(self, exc_type, exc_val, exc_tb): pass
    def set_attribute(self, key, value): pass
    def add_event(self, name, attributes=None): pass
    def record_exception(self, exception): pass
    def set_status(self, status): pass

class NoOpLogger:
    def info(self, event, **kwargs): pass
    def error(self, event, **kwargs): pass
    def debug(self, event, **kwargs): pass
    def warning(self, event, **kwargs): pass
    def critical(self, event, **kwargs): pass

# Factory function
def get_telemetry(name):
    return TracingFacade(name), LoggingFacade(name)
```

This implementation:

- Checks for dependency availability
- Provides no-op implementations when dependencies are missing
- Integrates OpenTelemetry context with structlog
- Presents a unified API regardless of dependency availability

## 6. Recommendations for pynector

Based on the research, here are recommendations for implementing OpenTelemetry
tracing and structured logging in the pynector project:

### 6.1 Architecture

1. **Make dependencies optional**:
   - Declare OpenTelemetry and structlog as optional dependencies in
     `pyproject.toml`
   - Provide no-op implementations when dependencies are missing

2. **Create a telemetry facade**:
   - Implement a facade pattern to abstract away the dependencies
   - Provide a stable API regardless of dependency availability

3. **Ensure context propagation**:
   - Use OpenTelemetry context propagation in async code
   - Provide helpers for manual context propagation in complex scenarios

4. **Support flexible configuration**:
   - Respect OpenTelemetry environment variables
   - Allow programmatic configuration overrides
   - Provide sensible defaults

### 6.2 Implementation Strategy

1. **Start with the facade layer**:
   - Implement the telemetry facade module first
   - Define the public API for tracing and logging

2. **Add no-op implementations**:
   - Implement no-op classes for when dependencies are missing
   - Ensure they match the API of the real implementations

3. **Implement context propagation**:
   - Add helpers for context propagation in async code
   - Test with different async patterns (asyncio, thread pools, etc.)

4. **Add configuration support**:
   - Implement configuration functions that respect environment variables
   - Add programmatic configuration options

5. **Integrate with the rest of the library**:
   - Use the telemetry facade throughout the library
   - Add instrumentation to key operations

### 6.3 Example Usage

The final API should be simple to use:

```python
from pynector.telemetry import get_telemetry

# Get tracer and logger
tracer, logger = get_telemetry("pynector.module")

async def process_data(data):
    # Log with structured data
    logger.info("processing_data", data_size=len(data))

    # Create a span for the operation
    with tracer.start_as_current_span("process_data", attributes={"data_size": len(data)}) as span:
        try:
            result = await perform_processing(data)
            span.set_attribute("result_size", len(result))
            logger.info("processing_complete", result_size=len(result))
            return result
        except Exception as e:
            # Record exception in span and log
            span.record_exception(e)
            logger.error("processing_failed", error=str(e))
            raise
```

This API:

- Is simple and intuitive
- Works regardless of whether dependencies are available
- Integrates tracing and logging
- Handles async code properly

## 7. Conclusion

Integrating OpenTelemetry tracing and structured logging in an async Python
library requires careful consideration of optional dependencies, context
propagation, and configuration options. By using the patterns and approaches
outlined in this report, the pynector project can implement a robust telemetry
system that:

- Works with or without dependencies
- Properly handles async context propagation
- Supports flexible configuration
- Integrates tracing and logging

The recommended approach uses a facade pattern to abstract away the
dependencies, provides no-op implementations when dependencies are missing, and
ensures proper context propagation in async code. This approach balances
flexibility, usability, and robustness, making it suitable for a wide range of
use cases.

## 8. References

1. OpenTelemetry Python Documentation (search:
   exa-opentelemetry-python.readthedocs.io)
2. OpenTelemetry Python GitHub Repository (search:
   exa-github.com/open-telemetry/opentelemetry-python)
3. OpenTelemetry Environment Variable Specification (search:
   exa-opentelemetry.io/docs/specs/otel/configuration/sdk-environment-variables/)
4. Structlog Documentation (search: exa-www.structlog.org/en/stable/)
5. Python Optional Imports (search: exa-github.com/kevinsawade/optional_imports)
6. Python Fallback Pattern (search: exa-github.com/weilueluo/pyfallback)
7. Python No-op Pattern (search: exa-github.com/joshp123/python-noop)
8. Advanced Tracing Examples (search:
   exa-docs.arize.com/arize/llm-tracing/how-to-tracing-manual/advanced-tracing-otel-examples)
9. OpenTelemetry Context Propagation (search:
   exa-opentelemetry.io/docs/concepts/context-propagation/)
