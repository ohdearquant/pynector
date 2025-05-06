# Technical Design Specification: Core Pynector Class

**Issue:** #6\
**Author:** pynector-architect\
**Date:** 2025-05-05\
**Status:** Draft

## 1. Introduction

This Technical Design Specification (TDS) defines the architecture and
implementation details for the core `Pynector` class in the pynector project.
The design integrates the Transport Abstraction Layer ([TDS-1.md](TDS-1.md)),
Structured Concurrency ([TDS-2.md](TDS-2.md)), and Optional Observability
([TDS-3.md](TDS-3.md)) into a cohesive, user-friendly API.

### 1.1 Purpose

The core `Pynector` class provides a unified, high-level interface that:

- Abstracts away the details of different transport mechanisms
- Leverages structured concurrency for efficient parallel operations
- Integrates optional observability features for monitoring and debugging
- Manages resources and connections properly throughout their lifecycle
- Offers a clean, intuitive, and Pythonic API

### 1.2 Scope

This specification covers:

- The public API of the `Pynector` class
- Configuration management and initialization
- Integration with transport, concurrency, and observability components
- Resource lifecycle management
- Error handling strategy

### 1.3 Design Principles

The design adheres to the following principles:

1. **Simplicity:** The API should be easy to understand and use while hiding
   implementation complexity
2. **Flexibility:** The implementation should support various transport types
   and configurations
3. **Resource Safety:** All resources should be properly managed throughout
   their lifecycle
4. **Performance:** Operations should be efficient, especially for batch
   requests
5. **Observability:** All operations should be traceable and loggable when
   enabled
6. **Pythonic:** The API should follow Python conventions and idioms

## 2. Architecture Overview

The core `Pynector` class acts as a facade that coordinates between different
components:

1. **Transport Layer:** Handles communication with remote endpoints
2. **Concurrency Layer:** Manages parallel operations and timeouts
3. **Observability Layer:** Provides optional tracing and logging

### 2.1 Component Diagram

```
┌─────────────────────────────────────┐
│           Client Application        │
└───────────────┬─────────────────────┘
                │ uses
                ▼
┌─────────────────────────────────────┐
│           Pynector                  │
├─────────────────────────────────────┤
│  - __init__                         │
│  - request()                        │
│  - batch_request()                  │
│  - aclose()                         │
│  - __aenter__/__aexit__             │
└──┬──────────────┬──────────────┬────┘
   │ creates      │ uses         │ uses
   ▼              ▼              ▼
┌─────────┐ ┌─────────────┐ ┌──────────┐
│Transport│ │  AnyIO      │ │Telemetry │
│Factory  │ │Task Groups  │ │Facade    │
└─────────┘ └─────────────┘ └──────────┘
   │ creates
   ▼
┌─────────┐
│Transport│
│Instance │
└─────────┘
```

### 2.2 Dependency Flow

The core `Pynector` class has the following dependencies:

- **Direct dependencies:**
  - `TransportFactory` from the Transport Abstraction Layer
  - Task groups and timeouts from AnyIO
  - `get_telemetry()` function from the Telemetry Facade

- **Indirect dependencies:**
  - Concrete transport implementations
  - OpenTelemetry and structlog (optional)

## 3. Pynector Class Design

### 3.1 Public API

```python
class Pynector:
    """
    The core client class for making requests through various transports with support for
    batch processing, timeouts, and optional observability.
    """

    def __init__(
        self,
        transport: Optional[TransportProtocol] = None,
        transport_type: str = "http",
        enable_telemetry: bool = True,
        config: Optional[Dict[str, Any]] = None,
        **transport_options
    ):
        """Initialize the Pynector instance.

        Args:
            transport: Optional pre-configured transport instance to use.
            transport_type: Type of transport to create if transport is not provided.
            enable_telemetry: Whether to enable telemetry features.
            config: Configuration options for the client.
            **transport_options: Additional options passed to the transport factory.
        """
        ...

    async def request(
        self,
        data: Any,
        timeout: Optional[float] = None,
        **options
    ) -> Any:
        """Send a single request and return the response.

        Args:
            data: The data to send.
            timeout: Optional timeout in seconds for this specific request.
            **options: Additional options for the request.

        Returns:
            The response data.

        Raises:
            TransportError: If there is an error with the transport.
            TimeoutError: If the request times out.
            PynectorError: For other errors.
        """
        ...

    async def batch_request(
        self,
        requests: List[Tuple[Any, Dict]],
        max_concurrency: Optional[int] = None,
        timeout: Optional[float] = None,
        raise_on_error: bool = False,
        **options
    ) -> List[Any]:
        """Send multiple requests in parallel and return the responses.

        Args:
            requests: List of (data, options) tuples.
            max_concurrency: Maximum number of concurrent requests.
            timeout: Optional timeout in seconds for the entire batch.
            raise_on_error: Whether to raise on the first error.
            **options: Additional options for all requests.

        Returns:
            List of responses or exceptions.

        Raises:
            TimeoutError: If the batch times out and raise_on_error is True.
            PynectorError: For other errors if raise_on_error is True.
        """
        ...

    async def aclose(self) -> None:
        """Close the Pynector instance and release resources."""
        ...

    async def __aenter__(self) -> 'Pynector':
        """Enter the async context."""
        ...

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType]
    ) -> None:
        """Exit the async context."""
        ...
```

### 3.2 Configuration Management

The `Pynector` class supports configuration through a hierarchy of sources:

1. **Explicit parameters:** Values provided directly to methods
2. **Instance configuration:** Values provided during initialization
3. **Environment variables:** Values from environment variables
4. **Default values:** Sensible defaults for all options

```python
def _get_config(self, key: str, default: Any = None) -> Any:
    """Get a configuration value from the hierarchy."""
    # 1. Check instance configuration
    if key in self._config:
        return self._config[key]

    # 2. Check environment variables
    env_key = f"PYNECTOR_{key.upper()}"
    if env_key in os.environ:
        return os.environ[env_key]

    # 3. Return default value
    return default
```

### 3.3 Initialization Logic

The initialization process involves:

1. Storing configuration and options
2. Setting up telemetry (if enabled)
3. Creating or storing the transport instance
4. Validating the configuration

```python
def __init__(
    self,
    transport: Optional[TransportProtocol] = None,
    transport_type: str = "http",
    enable_telemetry: bool = True,
    config: Optional[Dict[str, Any]] = None,
    **transport_options
):
    """Initialize the Pynector instance."""
    # Store configuration
    self._config = config or {}
    self._transport_type = transport_type
    self._transport_options = transport_options

    # Set up transport
    self._transport = transport
    self._owns_transport = transport is None
    self._transport_initialized = False

    # Set up telemetry
    self._tracer, self._logger = get_telemetry("pynector.core") if enable_telemetry else (None, None)

    # Validate configuration
    self._validate_config()
```

### 3.4 Resource Management Lifecycle

The `Pynector` class manages resources through async context management:

```python
async def __aenter__(self) -> 'Pynector':
    """Enter the async context."""
    transport = await self._get_transport()
    if self._owns_transport:
        await transport.__aenter__()
    return self

async def __aexit__(
    self,
    exc_type: Optional[Type[BaseException]],
    exc_val: Optional[BaseException],
    exc_tb: Optional[TracebackType]
) -> None:
    """Exit the async context."""
    if self._owns_transport and self._transport is not None:
        await self._transport.__aexit__(exc_type, exc_val, exc_tb)

async def aclose(self) -> None:
    """Close the Pynector instance and release resources."""
    if self._owns_transport and self._transport is not None:
        await self._transport.disconnect()
        self._transport = None
        self._transport_initialized = False
```

## 4. Integration of Transports

### 4.1 Transport Factory Usage

The `Pynector` class uses the `TransportFactory` to create transport instances:

```python
async def _get_transport(self) -> TransportProtocol:
    """Get or create a transport instance."""
    if self._transport is None or not self._transport_initialized:
        # Get transport factory
        factory_registry = get_transport_factory_registry()
        factory = factory_registry.get(self._transport_type)

        # Create transport
        if self._transport is None:
            self._transport = factory.create_transport(**self._transport_options)

        # Connect the transport
        await self._transport.connect()
        self._transport_initialized = True

    return self._transport
```

### 4.2 Transport Selection

Transport selection is based on the `transport_type` parameter and can be
overridden by providing a pre-configured transport instance:

```python
# Using the default HTTP transport
client = Pynector()

# Using a WebSocket transport
client = Pynector(transport_type="websocket", url="wss://example.com/ws")

# Using a pre-configured transport
custom_transport = CustomTransport(...)
client = Pynector(transport=custom_transport)
```

### 4.3 Transport Configuration Options

Transport configuration options are passed through to the transport factory:

```python
# HTTP transport configuration
client = Pynector(
    transport_type="http",
    base_url="https://api.example.com",
    headers={"Authorization": "Bearer token"},
    timeout=30.0
)
```

## 5. Integration of Structured Concurrency

### 5.1 Batch Request Implementation

Batch requests are implemented using AnyIO task groups to run multiple requests
concurrently:

```python
async def batch_request(
    self,
    requests: List[Tuple[Any, Dict]],
    max_concurrency: Optional[int] = None,
    timeout: Optional[float] = None,
    raise_on_error: bool = False,
    **options
) -> List[Any]:
    """Send multiple requests in parallel and return the responses."""
    results = [None] * len(requests)

    # Create a capacity limiter if max_concurrency is specified
    limiter = anyio.CapacityLimiter(max_concurrency) if max_concurrency else None

    async def process_request(index, data, request_options):
        try:
            if limiter:
                async with limiter:
                    result = await self.request(data, **(options | request_options))
            else:
                result = await self.request(data, **(options | request_options))
            results[index] = result
        except Exception as e:
            results[index] = e
            if raise_on_error:
                raise

    # Apply timeout if specified
    if timeout:
        async with anyio.fail_after(timeout):
            async with anyio.create_task_group() as tg:
                for i, (data, request_options) in enumerate(requests):
                    await tg.start_soon(process_request, i, data, request_options)
    else:
        async with anyio.create_task_group() as tg:
            for i, (data, request_options) in enumerate(requests):
                await tg.start_soon(process_request, i, data, request_options)

    return results
```

### 5.2 Timeout Handling

Timeouts are handled using AnyIO's `fail_after` and `move_on_after` functions:

```python
async def request(
    self,
    data: Any,
    timeout: Optional[float] = None,
    **options
) -> Any:
    """Send a single request and return the response."""
    transport = await self._get_transport()

    # Get timeout from options, instance config, or default
    if timeout is None:
        timeout = self._get_config("timeout")

    if timeout:
        # Use fail_after to raise an exception on timeout
        async with anyio.fail_after(float(timeout)):
            return await self._perform_request(transport, data, **options)
    else:
        return await self._perform_request(transport, data, **options)
```

### 5.3 Concurrency Limits

Concurrency limits are implemented using AnyIO's `CapacityLimiter`:

```python
# Limiting concurrent requests to 10
results = await client.batch_request(
    requests,
    max_concurrency=10
)
```

## 6. Integration of Observability

### 6.1 Telemetry Integration

The `Pynector` class integrates with the telemetry facade to provide optional
observability:

```python
def __init__(
    self,
    transport: Optional[TransportProtocol] = None,
    transport_type: str = "http",
    enable_telemetry: bool = True,
    config: Optional[Dict[str, Any]] = None,
    **transport_options
):
    """Initialize the Pynector instance."""
    # ...
    self._tracer, self._logger = get_telemetry("pynector.core") if enable_telemetry else (None, None)
    # ...
```

### 6.2 Span Creation and Management

Spans are created for both single requests and batch requests:

```python
async def request(self, data: Any, timeout: Optional[float] = None, **options) -> Any:
    """Send a single request and return the response."""
    if self._tracer:
        with self._tracer.start_as_current_span("pynector.request") as span:
            span.set_attribute("request.size", len(str(data)))
            try:
                result = await self._perform_request_with_timeout(data, timeout, **options)
                span.set_attribute("response.size", len(str(result)))
                return result
            except Exception as e:
                span.record_exception(e)
                raise
    else:
        return await self._perform_request_with_timeout(data, timeout, **options)
```

### 6.3 Context Propagation

Context propagation is ensured across async boundaries:

```python
async def batch_request(
    self,
    requests: List[Tuple[Any, Dict]],
    max_concurrency: Optional[int] = None,
    timeout: Optional[float] = None,
    raise_on_error: bool = False,
    **options
) -> List[Any]:
    """Send multiple requests in parallel and return the responses."""
    results = [None] * len(requests)

    if self._tracer:
        with self._tracer.start_as_current_span("pynector.batch_request") as span:
            span.set_attribute("request.count", len(requests))
            # Capture current context with the active span
            from opentelemetry.context import attach, detach, get_current
            context = get_current()

            async def process_request(index, data, request_options):
                # Attach the captured context to this task
                token = attach(context)
                try:
                    # ... process request ...
                finally:
                    # Always detach the context when done
                    detach(token)

            # ... run task group ...
    else:
        # ... regular implementation without tracing ...

    return results
```

### 6.4 Logging with Trace Context

Logging includes trace context for correlation:

```python
async def request(self, data: Any, timeout: Optional[float] = None, **options) -> Any:
    """Send a single request and return the response."""
    if self._logger:
        self._logger.info(
            "request.start",
            data_size=len(str(data)),
            timeout=timeout,
            options=str(options)
        )

    try:
        result = await self._perform_request_with_timeout(data, timeout, **options)

        if self._logger:
            self._logger.info(
                "request.complete",
                data_size=len(str(data)),
                result_size=len(str(result))
            )

        return result
    except Exception as e:
        if self._logger:
            self._logger.error(
                "request.error",
                error=str(e),
                error_type=type(e).__name__
            )
        raise
```

## 7. Error Handling Strategy

### 7.1 Common Error Types

The `Pynector` class defines a hierarchy of error types:

```python
class PynectorError(Exception):
    """Base class for all Pynector errors."""
    pass

class TransportError(PynectorError):
    """Error related to transport operations."""
    pass

class ConfigurationError(PynectorError):
    """Error related to configuration."""
    pass

class TimeoutError(PynectorError):
    """Error related to timeouts."""
    pass
```

### 7.2 Error Propagation

Errors are propagated from the transport layer and wrapped in appropriate
`PynectorError` types:

```python
async def _perform_request(self, transport: TransportProtocol, data: Any, **options) -> Any:
    """Perform the actual request."""
    try:
        await transport.send(data, **options)
        result = b""
        async for chunk in transport.receive():
            result += chunk
        return result
    except ConnectionError as e:
        raise TransportError(f"Connection error: {e}") from e
    except Exception as e:
        if isinstance(e, PynectorError):
            raise
        raise PynectorError(f"Unexpected error: {e}") from e
```

### 7.3 Retry Policies

The `Pynector` class supports retry policies for handling transient errors:

```python
async def request_with_retry(
    self,
    data: Any,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    **options
) -> Any:
    """Send a request with retry for transient errors."""
    last_error = None

    for attempt in range(max_retries):
        try:
            return await self.request(data, **options)
        except TransportError as e:
            last_error = e
            if attempt < max_retries - 1:
                # Wait before retrying (with exponential backoff)
                await anyio.sleep(retry_delay * (2 ** attempt))
            else:
                break

    raise last_error
```

## 8. Implementation Considerations

### 8.1 Performance Optimizations

To ensure good performance:

1. **Lazy Initialization:** Transport instances are created and connected only
   when needed
2. **Reusable Connections:** Transport connections are reused across multiple
   requests
3. **Efficient Batch Processing:** Task groups and capacity limiters are used
   for efficient parallel processing
4. **Buffer Management:** Response chunks are efficiently handled to minimize
   memory usage

### 8.2 Testing Strategy

The testing strategy includes:

1. **Unit Tests:** Testing individual components with mocked dependencies
2. **Integration Tests:** Testing the interaction between components
3. **End-to-End Tests:** Testing the complete flow with real transports
4. **Performance Tests:** Testing the performance of batch requests with
   different concurrency limits

### 8.3 Backward Compatibility

The `Pynector` class is designed to maintain backward compatibility:

1. **Optional Parameters:** New features are added as optional parameters
2. **Deprecated Methods:** Old methods are marked as deprecated but maintained
3. **Version Checks:** Version-specific behavior is controlled through
   configuration

## 9. Example Usage

### 9.1 Simple Request

```python
from pynector import Pynector

async def main():
    # Create a client
    async with Pynector(
        transport_type="http",
        base_url="https://api.example.com"
    ) as client:
        # Make a request
        result = await client.request({"query": "data"})
        print(result)
```

### 9.2 Batch Request

```python
from pynector import Pynector

async def main():
    # Create a client
    async with Pynector(
        transport_type="http",
        base_url="https://api.example.com"
    ) as client:
        # Prepare multiple requests
        requests = [
            ({"query": "data1"}, {}),
            ({"query": "data2"}, {"timeout": 5.0}),
            ({"query": "data3"}, {"headers": {"X-Custom": "value"}})
        ]

        # Send batch request
        results = await client.batch_request(
            requests,
            max_concurrency=10,
            timeout=30.0
        )

        # Process results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Request {i} failed: {result}")
            else:
                print(f"Request {i} succeeded: {result}")
```

### 9.3 With Optional Features

```python
from pynector import Pynector, configure_telemetry

async def main():
    # Configure telemetry
    configure_telemetry(
        service_name="my-service",
        resource_attributes={"deployment.environment": "production"}
    )

    # Create a client with telemetry enabled
    async with Pynector(
        transport_type="http",
        base_url="https://api.example.com",
        enable_telemetry=True
    ) as client:
        # Make a request (will be traced and logged)
        result = await client.request({"query": "data"})
        print(result)
```

## 10. Conclusion

The core `Pynector` class provides a unified, high-level interface for making
requests through various transports. By integrating the Transport Abstraction
Layer, Structured Concurrency, and Optional Observability, it offers a robust
and flexible solution that is both easy to use and powerful.

The design prioritizes a clean, Pythonic API while hiding the implementation
complexity. Through proper resource management, efficient batch processing, and
optional observability, it meets the needs of a wide range of use cases.

## 11. References

1. Research Report: Core Pynector Class API Design ([RR-6.md](../rr/RR-6.md))
   (search: internal-document)
2. Technical Design Specification: Transport Abstraction Layer
   ([TDS-1.md](TDS-1.md)) (search: internal-document)
3. Technical Design Specification: Structured Concurrency ([TDS-2.md](TDS-2.md))
   (search: internal-document)
4. Technical Design Specification: Optional Observability ([TDS-3.md](TDS-3.md))
   (search: internal-document)
5. Brett Cannon, "Designing an async API, from sans-I/O on up" (search:
   exa-snarky.ca/designing-an-async-api-from-sans-i-o-on-up)
6. Real Python, "Asynchronous context manager" (search:
   exa-realpython.com/ref/glossary/asynchronous-context-manager)
7. AnyIO Tasks Documentation (search:
   exa-anyio.readthedocs.io/en/latest/tasks.html)
8. OpenTelemetry Python Documentation (search:
   exa-opentelemetry-python.readthedocs.io)
9. Benhoyt, "Designing Pythonic library APIs" (search:
   exa-benhoyt.com/writings/python-api-design/)
10. Seth Michael Larson, "API Design for Optional Async Context Managed
    Resources" (search:
    exa-dev.to/sethmlarson/api-design-for-optional-async-context-managed-resources-4gm9)
