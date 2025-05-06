# Research Report: Core Pynector Class API Design

**Issue:** #6\
**Author:** pynector-researcher\
**Date:** 2025-05-05\
**Status:** Complete

## 1. Executive Summary

This research report explores best practices for designing the core `Pynector`
class API, focusing on integrating transports, structured concurrency, and
optional observability. The goal is to provide a solid foundation for
implementing a clean, intuitive, and flexible API that follows Python best
practices and provides a consistent interface for users.

Key findings:

- A facade pattern with adapter classes provides the most flexible approach for
  integrating different transports
- Structured concurrency with AnyIO task groups enables efficient batch request
  processing
- Optional observability can be implemented using a telemetry facade with no-op
  fallbacks
- Configuration management should support both environment variables and
  programmatic configuration
- Resource lifecycle management is best handled with async context managers
- A clean public API should prioritize simplicity, consistency, and
  discoverability

## 2. Integration of Transports

### 2.1 Transport Abstraction Layer

As established in RR-1, the transport abstraction layer should use Protocol
classes to define interfaces and async context managers for resource management.
The core `Pynector` class should integrate with this transport layer in a way
that allows for flexibility in transport selection while maintaining a
consistent API.

**Source:**
[Transport Abstraction Layers in Python (RR-1.md)](reports/rr/RR-1.md)

> "By combining the sans-I/O pattern, Protocol classes, and async context
> management, pynector can create a flexible, maintainable, and type-safe
> transport layer."

### 2.2 Transport Integration Patterns

Several patterns exist for integrating transports into a core API:

1. **Direct Integration:** The core class directly instantiates and manages
   transport instances
2. **Dependency Injection:** Transports are created externally and passed to the
   core class
3. **Factory Pattern:** The core class uses a factory to create appropriate
   transport instances
4. **Adapter Pattern:** The core class uses adapters to normalize different
   transport interfaces

Based on the research, the adapter pattern provides the most flexibility while
maintaining a consistent API. This approach is demonstrated in RR-5 for SDK
transports:

        async with transport:
            await transport.send(data, **options)
            async for chunk in transport.receive():
                # Process response
                pass
        
    async def batch_request(self, requests: List[Tuple[Any, Dict]], **options) -> List[Any]:
        """Send multiple requests in parallel and return the responses."""
        results = [None] * len(requests)
        
        async def process_request(index, data, request_options):
            try:
                result = await self.request(data, **(options | request_options))
                results[index] = result
            except Exception as e:
                results[index] = e
        
        async with anyio.create_task_group() as tg:
            for i, (data, request_options) in enumerate(requests):
                await tg.start_soon(process_request, i, data, request_options)
                
        return results

````
This implementation ensures that all requests are properly managed and that errors in one request don't affect others.

### 3.3 Timeout Handling

Timeout handling is crucial for batch requests. AnyIO provides two main approaches:

1. **move_on_after:** Exits the context block after the specified timeout without raising an exception
2. **fail_after:** Raises a `TimeoutError` if the operation exceeds the specified timeout

**Source:** [Structured Concurrency Patterns in AnyIO (RR-2.md)](reports/rr/RR-2.md)

> "Networked operations can often take a long time, and you usually want to set up some kind of a timeout to ensure that your application doesn't stall forever. There are two principal ways to do this: `move_on_after()` and `fail_after()`."

The `Pynector` class should support both approaches:

```python
async def batch_request_with_timeout(
    self,
    requests: List[Tuple[Any, Dict]],
    timeout: float,
    fail_on_timeout: bool = False,
    **options
) -> List[Any]:
    """Send multiple requests with a timeout."""
    if fail_on_timeout:
        async with anyio.fail_after(timeout):
            return await self.batch_request(requests, **options)
    else:
        with anyio.move_on_after(timeout) as scope:
            results = await self.batch_request(requests, **options)
            if scope.cancelled_caught:
                # Handle timeout (e.g., fill remaining results with TimeoutError)
                pass
            return results
````

## 4. Optional Observability

### 4.1 Telemetry Facade

As established in RR-3, optional observability can be implemented using a
telemetry facade with no-op fallbacks. This approach allows the `Pynector` class
to provide observability features without requiring dependencies.

**Source:**
[OpenTelemetry Tracing and Structured Logging in Async Python Libraries (RR-3.md)](reports/rr/RR-3.md)

> "By using the patterns and approaches outlined in this report, the pynector
> project can implement a robust telemetry system that works with or without
> dependencies, properly handles async context propagation, supports flexible
> configuration, and integrates tracing and logging."

### 4.2 Integration with Pynector

The core `Pynector` class should integrate with the telemetry facade to provide
observability:

```python
from pynector.telemetry import get_telemetry

class Pynector:
    def __init__(
        self,
        # ... other parameters ...
        enable_telemetry: bool = True,
    ):
        # ... other initialization ...
        self._tracer, self._logger = get_telemetry("pynector.core") if enable_telemetry else (None, None)
        
    async def request(self, data: Any, **options) -> Any:
        """Send a single request and return the response."""
        if self._tracer:
            with self._tracer.start_as_current_span("pynector.request") as span:
                span.set_attribute("request.size", len(data))
                try:
                    result = await self._perform_request(data, **options)
                    span.set_attribute("response.size", len(result))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    raise
        else:
            return await self._perform_request(data, **options)
```

This approach ensures that observability is optional and doesn't affect the core
functionality.

### 4.3 Context Propagation

Context propagation is crucial for observability in async code. The `Pynector`
class should ensure that context is properly propagated across async boundaries:

**Source:**
[OpenTelemetry Tracing and Structured Logging in Async Python Libraries (RR-3.md)](reports/rr/RR-3.md)

> "For async libraries, a combination of automatic and manual context
> propagation is recommended."

```python
async def batch_request(self, requests: List[Tuple[Any, Dict]], **options) -> List[Any]:
    """Send multiple requests in parallel and return the responses."""
    results = [None] * len(requests)
    
    if self._tracer:
        with self._tracer.start_as_current_span("pynector.batch_request") as span:
            span.set_attribute("request.count", len(requests))
            # Capture current context with the active span
            context = get_current()
            
            async def process_request(index, data, request_options):
                # Attach the captured context to this task
                token = attach(context)
                try:
                    result = await self.request(data, **(options | request_options))
                    results[index] = result
                except Exception as e:
                    results[index] = e
                finally:
                    # Always detach the context when done
                    detach(token)
            
            async with anyio.create_task_group() as tg:
                for i, (data, request_options) in enumerate(requests):
                    await tg.start_soon(process_request, i, data, request_options)
    else:
        # Regular implementation without tracing
        # ...
                
    return results
```

## 5. Configuration Management

### 5.1 Configuration Options

Configuration management is a critical aspect of API design. The `Pynector`
class should support both environment variables and programmatic configuration.

**Source:**
[Best Practices for Working with Configuration in Python Applications](https://tech.preferred.jp/en/blog/working-with-configuration-in-python/)
(search: exa-tech.preferred.jp/en/blog/working-with-configuration-in-python/)

> "I will present some guiding principles for program-internal configuration
> handling that proved useful in the past and that I would like to recommend for
> anyone developing small to medium size applications."

### 5.2 Configuration Hierarchy

The configuration hierarchy should be:

1. **Explicit parameters:** Values provided directly to methods
2. **Instance configuration:** Values provided during initialization
3. **Environment variables:** Values from environment variables
4. **Default values:** Sensible defaults for all options

```python
import os
from typing import Any, Dict, Optional

class Pynector:
    def __init__(
        self,
        # ... other parameters ...
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the Pynector instance with configuration."""
        self._config = config or {}
        
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

### 5.3 Configuration Validation

Configuration validation is important to ensure that the API is used correctly.
The `Pynector` class should validate configuration values and provide helpful
error messages:

```python
def _validate_config(self) -> None:
    """Validate the configuration."""
    # Example validation
    timeout = self._get_config("timeout")
    if timeout is not None:
        try:
            timeout = float(timeout)
            if timeout <= 0:
                raise ValueError("Timeout must be positive")
        except ValueError:
            raise ValueError(f"Invalid timeout value: {timeout}")
```

## 6. Resource Lifecycle Management

### 6.1 Async Context Manager

Async context managers provide a clean way to manage resources in asynchronous
code. The `Pynector` class should implement the async context manager protocol
to ensure proper resource management:

**Source:**
[Asynchronous context manager | Python Glossary](https://realpython.com/ref/glossary/asynchronous-context-manager/)
(search: exa-realpython.com/ref/glossary/asynchronous-context-manager/)

> "In Python, an asynchronous context manager is an object that creates a
> context that allows you to allocate resources before running asynchronous code
> and release them after. To use this type of context manager, you need the
> async with statement."

```python
class Pynector:
    # ... other methods ...
    
    async def __aenter__(self) -> 'Pynector':
        """Enter the async context."""
        transport = await self._get_transport()
        if self._owns_transport:
            await transport.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the async context."""
        if self._owns_transport and self._transport is not None:
            await self._transport.__aexit__(exc_type, exc_val, exc_tb)
```

### 6.2 Resource Cleanup

Proper resource cleanup is essential for async applications. The `Pynector`
class should ensure that all resources are properly cleaned up, even in the case
of exceptions:

**Source:**
[API Design for Optional Async Context Managed Resources](https://dev.to/sethmlarson/api-design-for-optional-async-context-managed-resources-4gm9)
(search:
exa-dev.to/sethmlarson/api-design-for-optional-async-context-managed-resources-4gm9)

> "I had a discussion on Twitter with Mike Bayer, author of SQLAlchemy, about
> API design regarding async functions that return a resource to optionally be
> used as a async context manager."

```python
async def close(self) -> None:
    """Close the Pynector instance and release resources."""
    if self._owns_transport and self._transport is not None:
        await self._transport.disconnect()
        self._transport = None
```

### 6.3 Optional Context Management

The `Pynector` class should support both context-managed and non-context-managed
usage:

```python
# Context-managed usage
async with Pynector() as client:
    result = await client.request(data)
    
# Non-context-managed usage
client = Pynector()
try:
    result = await client.request(data)
finally:
    await client.close()
```

## 7. Clean Public API Design

### 7.1 API Design Principles

A clean public API should follow several key principles:

**Source:**
[Designing Pythonic library APIs](https://benhoyt.com/writings/python-api-design/)
(search: exa-benhoyt.com/writings/python-api-design/)

> "An easy-to-use API is what sold Requests back in 2011, and that's what
> continues to sell it today."

1. **Simplicity:** The API should be easy to understand and use
2. **Consistency:** The API should follow consistent patterns and naming
   conventions
3. **Discoverability:** The API should make it easy to discover available
   functionality
4. **Flexibility:** The API should be flexible enough to handle various use
   cases
5. **Pythonic:** The API should follow Python idioms and conventions

### 7.2 Method Naming and Parameters

Method naming and parameters should follow consistent patterns:

**Source:**
[Code Design Principles for Public APIs of Modules](https://code.kiwi.com/articles/code-design-principles-for-public-apis-of-modules/)
(search:
exa-code.kiwi.com/articles/code-design-principles-for-public-apis-of-modules/)

> "Think about what the 'direct object' of your function is, if we can use a
> grammar analogy for a minute here."

```python
# Good: Clear method names with appropriate parameters
async def request(self, data: Any, **options) -> Any:
    """Send a single request and return the response."""
    
async def batch_request(self, requests: List[Tuple[Any, Dict]], **options) -> List[Any]:
    """Send multiple requests in parallel and return the responses."""
    
# Bad: Unclear method names or inappropriate parameters
async def process(self, data: Any) -> Any:
    """Process data."""
    
async def multi(self, data_list: List[Any]) -> List[Any]:
    """Process multiple data items."""
```

### 7.3 Error Handling

Error handling should be consistent and informative:

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

### 7.4 Documentation

Documentation is a critical aspect of API design. The `Pynector` class should
have comprehensive docstrings and examples:

```python
class Pynector:
    """
    Pynector client for making requests through various transports.
    
    This class provides a high-level API for making requests through
    different transport mechanisms (HTTP, WebSocket, etc.) with support
    for batch processing, timeouts, and observability.
    
    Examples:
        # Simple request
        async with Pynector() as client:
            result = await client.request(data)
            
        # Batch request
        async with Pynector() as client:
            results = await client.batch_request([
                (data1, {}),
                (data2, {"timeout": 5.0}),
            ])
    """
    
    def __init__(
        self,
        transport: Optional[TransportProtocol] = None,
        transport_type: str = "http",
        enable_telemetry: bool = True,
        config: Optional[Dict[str, Any]] = None,
        **transport_options
    ):
        """
        Initialize the Pynector instance.
        
        Args:
            transport: Optional transport instance to use.
            transport_type: Type of transport to create if not provided.
            enable_telemetry: Whether to enable telemetry.
            config: Configuration options.
            **transport_options: Additional options for the transport.
        """
        # ...
```

## 8. Batch Request Functionality

### 8.1 Batch Request Patterns

Batch request functionality is essential for efficient processing of multiple
requests. Several patterns exist for implementing batch requests:

**Source:**
[GitHub - hussein-awala/async-batcher](https://github.com/hussein-awala/async-batcher)
(search: exa-github.com/hussein-awala/async-batcher)

> "Storing multiple records in a database in a single query to optimize the I/O
> operations... Sending multiple messages in a single request to optimize the
> network operations."

1. **Parallel Processing:** Process multiple requests in parallel using task
   groups
2. **Batched API Calls:** Combine multiple requests into a single API call
3. **Dynamic Batching:** Dynamically batch requests based on arrival time and
   capacity

### 8.2 AnyIO Implementation

AnyIO provides the necessary primitives for implementing efficient batch request
functionality:

**Source:**
[AnyIO Tasks Documentation](https://anyio.readthedocs.io/en/latest/tasks.html)
(search: exa-anyio.readthedocs.io/en/latest/tasks.html)

> "A task group is an asynchronous context manager that makes sure that all its
> child tasks are finished one way or another after the context block is
> exited."

```python
async def batch_request(
    self,
    requests: List[Tuple[Any, Dict]],
    max_concurrency: Optional[int] = None,
    **options
) -> List[Any]:
    """Send multiple requests with optional concurrency limit."""
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
    
    async with anyio.create_task_group() as tg:
        for i, (data, request_options) in enumerate(requests):
            await tg.start_soon(process_request, i, data, request_options)
            
    return results
```

### 8.3 Error Handling in Batch Requests

Error handling in batch requests requires special consideration. The `Pynector`
class should provide options for handling errors in batch requests:

```python
async def batch_request(
    self,
    requests: List[Tuple[Any, Dict]],
    raise_on_error: bool = False,
    **options
) -> List[Any]:
    """Send multiple requests with error handling options."""
    results = [None] * len(requests)
    
    async def process_request(index, data, request_options):
        try:
            result = await self.request(data, **(options | request_options))
            results[index] = result
        except Exception as e:
            results[index] = e
            if raise_on_error:
                raise
    
    async with anyio.create_task_group() as tg:
        for i, (data, request_options) in enumerate(requests):
            await tg.start_soon(process_request, i, data, request_options)
            
    return results
```

## 9. Recommendations for pynector

Based on the research, here are recommendations for implementing the core
`Pynector` class API:

### 9.1 Architecture

1. **Implement a facade pattern with adapter classes:**
   - Create a core `Pynector` class that provides a consistent API
   - Use adapter classes for different transport types
   - Support both built-in and custom transports

2. **Use AnyIO for structured concurrency:**
   - Implement task groups for batch request processing
   - Provide timeout handling with both `move_on_after` and `fail_after`
   - Support concurrency limits with `CapacityLimiter`

3. **Implement optional observability:**
   - Create a telemetry facade with no-op fallbacks
   - Ensure proper context propagation across async boundaries
   - Provide tracing and logging integration

4. **Support flexible configuration:**
   - Allow both environment variables and programmatic configuration
   - Implement a configuration hierarchy
   - Validate configuration values

5. **Implement proper resource lifecycle management:**
   - Use async context managers for resource management
   - Ensure proper cleanup of resources
   - Support both context-managed and non-context-managed usage

### 9.2 Proposed Implementation

```python
from typing import Any, Dict, List, Optional, Tuple, Union
import os
import anyio
from contextlib import asynccontextmanager

from pynector.transports.protocol import TransportProtocol
from pynector.telemetry import get_telemetry
from pynector.errors import PynectorError, TransportError, ConfigurationError, TimeoutError

class Pynector:
    """
    Pynector client for making requests through various transports.
    
    This class provides a high-level API for making requests through
    different transport mechanisms (HTTP, WebSocket, etc.) with support
    for batch processing, timeouts, and observability.
    
    Examples:
        # Simple request
        async with Pynector() as client:
            result = await client.request(data)
            
        # Batch request
        async with Pynector() as client:
            results = await client.batch_request([
                (data1, {}),
                (data2, {"timeout": 5.0}),
            ])
    """
    
    def __init__(
        self,
        transport: Optional[TransportProtocol] = None,
        transport_type: str = "http",
        enable_telemetry: bool = True,
        config: Optional[Dict[str, Any]] = None,
        **transport_options
    ):
        """
        Initialize the Pynector instance.
        
        Args:
            transport: Optional transport instance to use.
            transport_type: Type of transport to create if not provided.
            enable_telemetry: Whether to enable telemetry.
            config: Configuration options.
            **transport_options: Additional options for the transport.
        """
        self._transport = transport
        self._transport_type = transport_type
        self._transport_options = transport_options
        self._owns_transport = transport is None
        self._config = config or {}
        self._tracer, self._logger = get_telemetry("pynector.core") if enable_telemetry else (None, None)
        self._validate_config()
        
    def _validate_config(self) -> None:
        """Validate the configuration."""
        # Example validation
        timeout = self._get_config("timeout")
        if timeout is not None:
            try:
                timeout = float(timeout)
                if timeout <= 0:
                    raise ConfigurationError("Timeout must be positive")
            except ValueError:
                raise ConfigurationError(f"Invalid timeout value: {timeout}")
                
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
        
    async def _get_transport(self) -> TransportProtocol:
        """Get or create a transport instance."""
        if self._transport is None:
            # Create transport based on type and options
            if self._transport_type == "http":
                from pynector.transports.http import HttpTransport
                self._transport = HttpTransport(**self._transport_options)
            elif self._transport_type == "websocket":
                from pynector.transports.websocket import WebSocketTransport
                self._transport = WebSocketTransport(**self._transport_options)
            # Add more transport types as needed
            else:
                raise ConfigurationError(f"Unsupported transport type: {self._transport_type}")
                
            # Connect the transport
            await self._transport.connect()
            
        return self._transport
        
    async def request(self, data: Any, **options) -> Any:
        """
        Send a single request and return the response.
        
        Args:
            data: The data to send.
            **options: Additional options for the request.
            
        Returns:
            The response data.
            
        Raises:
            TransportError: If there is an error with the transport.
            TimeoutError: If the request times out.
            PynectorError: For other errors.
        """
        if self._tracer:
            with self._tracer.start_as_current_span("pynector.request") as span:
                span.set_attribute("request.size", len(str(data)))
                try:
                    result = await self._perform_request(data, **options)
                    span.set_attribute("response.size", len(str(result)))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    raise
        else:
            return await self._perform_request(data, **options)
            
    async def _perform_request(self, data: Any, **options) -> Any:
        """Perform the actual request."""
        transport = await self._get_transport()
        
        # Get timeout from options or config
        timeout = options.pop("timeout", self._get_config("timeout"))
        
        if timeout:
            async with anyio.fail_after(float(timeout)):
                await transport.send(data, **options)
                result = b""
                async for chunk in transport.receive():
                    result += chunk
                return result
        else:
            await transport.send(data, **options)
            result = b""
            async for chunk in transport.receive():
                result += chunk
            return result
            
    async def batch_request(
        self,
        requests: List[Tuple[Any, Dict]],
        max_concurrency: Optional[int] = None,
        raise_on_error: bool = False,
        **options
    ) -> List[Any]:
        """
        Send multiple requests in parallel and return the responses.
        
        Args:
            requests: List of (data, options) tuples.
            max_concurrency: Maximum number of concurrent requests.
            raise_on_error: Whether to raise on the first error.
            **options: Additional options for all requests.
            
        Returns:
            List of responses or exceptions.
        """
        results = [None] * len(requests)
        
        # Create a capacity limiter if max_concurrency is specified
        limiter = anyio.CapacityLimiter(max_concurrency) if max_concurrency else None
        
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
                    finally:
                        # Always detach the context when done
                        detach(token)
                
                async with anyio.create_task_group() as tg:
                    for i, (data, request_options) in enumerate(requests):
                        await tg.start_soon(process_request, i, data, request_options)
        else:
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
            
    async with anyio.create_task_group() as tg:
                for i, (data, request_options) in enumerate(requests):
                    await tg.start_soon(process_request, i, data, request_options)
                    
        return results
        
    async def __aenter__(self) -> 'Pynector':
        """Enter the async context."""
        transport = await self._get_transport()
        if self._owns_transport:
            await transport.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the async context."""
        if self._owns_transport and self._transport is not None:
            await self._transport.__aexit__(exc_type, exc_val, exc_tb)
            
    async def close(self) -> None:
        """Close the Pynector instance and release resources."""
        if self._owns_transport and self._transport is not None:
            await self._transport.disconnect()
            self._transport = None
```

### 9.3 Implementation Considerations

1. **Error Handling:**
   - Provide detailed error messages with context
   - Translate transport-specific errors to Pynector-specific errors
   - Ensure proper error propagation through async boundaries

2. **Testing:**
   - Implement unit tests with mocked transports
   - Add integration tests with real transports
   - Test error handling, timeouts, and resource cleanup

3. **Performance:**
   - Benchmark batch request performance with different concurrency limits
   - Optimize resource usage for common operations
   - Consider connection pooling for high-volume scenarios

4. **Documentation:**
   - Provide comprehensive API documentation
   - Include examples for common use cases
   - Document error handling and troubleshooting

## 10. Conclusion

Designing the core `Pynector` class API requires careful consideration of
several key aspects: transport integration, structured concurrency, optional
observability, configuration management, resource lifecycle, and clean API
design. By following the patterns and best practices outlined in this report,
the pynector project can create a robust, flexible, and user-friendly API that
meets the needs of various use cases.

The recommended approach uses a facade pattern with adapter classes to integrate
different transports, AnyIO task groups for structured concurrency, a telemetry
facade with no-op fallbacks for optional observability, a configuration
hierarchy for flexible configuration, async context managers for resource
lifecycle management, and consistent naming and documentation for a clean public
API.

This design provides a solid foundation for implementing the core `Pynector`
class, ensuring that it is both powerful and easy to use while following Python
best practices and idioms.

## 11. References

1. Transport Abstraction Layers in Python (RR-1.md)
2. Structured Concurrency Patterns in AnyIO (RR-2.md)
3. OpenTelemetry Tracing and Structured Logging in Async Python Libraries
   (RR-3.md)
4. Implementing an Async HTTP Transport with httpx (RR-4.md)
5. Async SDK Transport Wrapper for OpenAI and Anthropic (RR-5.md)
6. Benhoyt, "Designing Pythonic library APIs" (search:
   exa-benhoyt.com/writings/python-api-design/)
7. Code Kiwi, "Code Design Principles for Public APIs of Modules" (search:
   exa-code.kiwi.com/articles/code-design-principles-for-public-apis-of-modules/)
8. Preferred Networks, "Best Practices for Working with Configuration in Python
   Applications" (search:
   exa-tech.preferred.jp/en/blog/working-with-configuration-in-python/)
9. Real Python, "Asynchronous context manager | Python Glossary" (search:
   exa-realpython.com/ref/glossary/asynchronous-context-manager/)
10. Seth Michael Larson, "API Design for Optional Async Context Managed
    Resources" (search:
    exa-dev.to/sethmlarson/api-design-for-optional-async-context-managed-resources-4gm9)
11. Hussein Awala, "async-batcher" (search:
    exa-github.com/hussein-awala/async-batcher)
12. AnyIO Documentation, "Tasks" (search:
    exa-anyio.readthedocs.io/en/latest/tasks.html)
13. Raymond Hettinger, "API design: Lessons Learned" (search:
    exa-pyvideo.org/europython-2011/api-design-lessons-learned.html)
