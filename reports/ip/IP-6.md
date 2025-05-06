# Implementation Plan: Core Pynector Class

**Issue:** #6\
**Author:** pynector-implementer\
**Date:** 2025-05-05\
**Status:** Draft

## 1. Introduction

This Implementation Plan (IP) outlines the detailed approach for implementing
the core `Pynector` class as specified in [TDS-6.md](../tds/TDS-6.md). The
implementation will integrate the Transport Abstraction Layer
([TDS-1.md](../tds/TDS-1.md)), Structured Concurrency
([TDS-2.md](../tds/TDS-2.md)), and Optional Observability
([TDS-3.md](../tds/TDS-3.md)) into a cohesive, user-friendly API.

### 1.1 Purpose

The purpose of this implementation plan is to:

- Define the file structure and organization
- Detail the implementation approach for each method
- Specify integration points with other components
- Outline error handling and resource management strategies
- Provide code snippets for key functionality

### 1.2 Scope

This implementation plan covers:

- The `Pynector` class implementation
- Configuration management
- Transport factory integration
- Concurrency patterns for batch requests
- Observability integration
- Error handling and resource management

## 2. File Structure

The core `Pynector` class will be implemented in the following file structure:

```
src/pynector/
├── __init__.py           # Public API exports
├── config.py             # Configuration utilities
├── errors.py             # Error definitions
└── client.py             # Core Pynector class implementation
```

### 2.1 Public API Exports

The `__init__.py` file will export the public API:

```python
# src/pynector/__init__.py

from pynector.client import Pynector
from pynector.errors import PynectorError, TransportError, ConfigurationError, TimeoutError
from pynector.telemetry import configure_telemetry

__all__ = [
    "Pynector",
    "PynectorError",
    "TransportError",
    "ConfigurationError",
    "TimeoutError",
    "configure_telemetry",
]
```

## 3. Error Definitions

The `errors.py` file will define the error hierarchy:

```python
# src/pynector/errors.py

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

## 4. Configuration Utilities

The `config.py` file will provide configuration utilities:

```python
# src/pynector/config.py

import os
from typing import Any, Dict, Optional

def get_env_config(key: str, default: Any = None) -> Any:
    """Get a configuration value from environment variables.

    Args:
        key: The configuration key (will be prefixed with PYNECTOR_)
        default: The default value if not found

    Returns:
        The configuration value
    """
    env_key = f"PYNECTOR_{key.upper()}"
    if env_key in os.environ:
        return os.environ[env_key]
    return default

def merge_configs(
    base: Dict[str, Any],
    override: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Merge configuration dictionaries.

    Args:
        base: The base configuration
        override: The override configuration

    Returns:
        The merged configuration
    """
    if override is None:
        return base.copy()

    result = base.copy()
    for key, value in override.items():
        if isinstance(value, dict) and key in result and isinstance(result[key], dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value

    return result
```

## 5. Core Pynector Class Implementation

The `client.py` file will implement the core `Pynector` class:

### 5.1 Imports and Type Definitions

```python
# src/pynector/client.py

import os
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar, Union
from types import TracebackType
import anyio

from pynector.config import get_env_config, merge_configs
from pynector.errors import PynectorError, TransportError, ConfigurationError, TimeoutError
from pynector.transport.protocol import TransportProtocol
from pynector.transport.factory import get_transport_factory_registry
from pynector.telemetry import get_telemetry

T = TypeVar('T')
```

### 5.2 Pynector Class Definition

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

### 5.3 Configuration Management

```python
    def _validate_config(self) -> None:
        """Validate the configuration."""
        # Validate transport type if we need to create a transport
        if self._owns_transport:
            factory_registry = get_transport_factory_registry()
            if self._transport_type not in factory_registry.get_registered_names():
                raise ConfigurationError(
                    f"Invalid transport type: {self._transport_type}. "
                    f"Available types: {', '.join(factory_registry.get_registered_names())}"
                )

    def _get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value from the hierarchy.

        Args:
            key: The configuration key
            default: The default value if not found

        Returns:
            The configuration value
        """
        # 1. Check instance configuration
        if key in self._config:
            return self._config[key]

        # 2. Check environment variables
        env_value = get_env_config(key)
        if env_value is not None:
            return env_value

        # 3. Return default value
        return default
```

### 5.4 Transport Management

```python
    async def _get_transport(self) -> TransportProtocol:
        """Get or create a transport instance.

        Returns:
            The transport instance

        Raises:
            ConfigurationError: If the transport cannot be created
        """
        if self._transport is None or not self._transport_initialized:
            try:
                # Get transport factory
                factory_registry = get_transport_factory_registry()
                factory = factory_registry.get(self._transport_type)

                # Create transport if needed
                if self._transport is None:
                    self._transport = factory.create_transport(**self._transport_options)

                # Connect the transport
                await self._transport.connect()
                self._transport_initialized = True

                if self._logger:
                    self._logger.info(
                        "transport.connected",
                        transport_type=self._transport_type,
                        owns_transport=self._owns_transport
                    )

            except Exception as e:
                if self._logger:
                    self._logger.error(
                        "transport.connection_failed",
                        transport_type=self._transport_type,
                        error=str(e),
                        error_type=type(e).__name__
                    )
                if isinstance(e, PynectorError):
                    raise
                raise ConfigurationError(f"Failed to initialize transport: {e}") from e

        return self._transport
```

### 5.5 Request Method

```python
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
        # Start span if tracing is enabled
        if self._tracer:
            with self._tracer.start_as_current_span("pynector.request") as span:
                span.set_attribute("request.size", len(str(data)))
                if options:
                    span.set_attribute("request.options", str(options))

                try:
                    result = await self._perform_request_with_timeout(data, timeout, **options)
                    span.set_attribute("response.size", len(str(result)))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    raise
        else:
            return await self._perform_request_with_timeout(data, timeout, **options)

    async def _perform_request_with_timeout(
        self,
        data: Any,
        timeout: Optional[float] = None,
        **options
    ) -> Any:
        """Perform a request with timeout handling.

        Args:
            data: The data to send
            timeout: Optional timeout in seconds
            **options: Additional options for the request

        Returns:
            The response data

        Raises:
            TimeoutError: If the request times out
            TransportError: If there is an error with the transport
            PynectorError: For other errors
        """
        # Log request if logging is enabled
        if self._logger:
            self._logger.info(
                "request.start",
                data_size=len(str(data)),
                timeout=timeout,
                options=str(options)
            )

        # Get timeout from options, instance config, or default
        if timeout is None:
            timeout = self._get_config("timeout")

        try:
            if timeout:
                # Use fail_after to raise an exception on timeout
                try:
                    async with anyio.fail_after(float(timeout)):
                        result = await self._perform_request(data, **options)
                except TimeoutError:
                    if self._logger:
                        self._logger.error(
                            "request.timeout",
                            timeout=timeout,
                            data_size=len(str(data))
                        )
                    raise TimeoutError(f"Request timed out after {timeout} seconds")
            else:
                result = await self._perform_request(data, **options)

            # Log success if logging is enabled
            if self._logger:
                self._logger.info(
                    "request.complete",
                    data_size=len(str(data)),
                    result_size=len(str(result))
                )

            return result

        except Exception as e:
            # Log error if logging is enabled
            if self._logger:
                self._logger.error(
                    "request.error",
                    error=str(e),
                    error_type=type(e).__name__
                )

            # Re-raise the exception
            raise

    async def _perform_request(self, data: Any, **options) -> Any:
        """Perform the actual request.

        Args:
            data: The data to send
            **options: Additional options for the request

        Returns:
            The response data

        Raises:
            TransportError: If there is an error with the transport
            PynectorError: For other errors
        """
        transport = await self._get_transport()

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

### 5.6 Batch Request Method

```python
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
        results = [None] * len(requests)

        # Start span if tracing is enabled
        if self._tracer:
            with self._tracer.start_as_current_span("pynector.batch_request") as span:
                span.set_attribute("request.count", len(requests))
                if max_concurrency:
                    span.set_attribute("max_concurrency", max_concurrency)
                if timeout:
                    span.set_attribute("timeout", timeout)

                try:
                    results = await self._perform_batch_request(
                        requests, max_concurrency, timeout, raise_on_error, **options
                    )
                    span.set_attribute("success_count", sum(1 for r in results if not isinstance(r, Exception)))
                    span.set_attribute("error_count", sum(1 for r in results if isinstance(r, Exception)))
                    return results
                except Exception as e:
                    span.record_exception(e)
                    raise
        else:
            return await self._perform_batch_request(
                requests, max_concurrency, timeout, raise_on_error, **options
            )

    async def _perform_batch_request(
        self,
        requests: List[Tuple[Any, Dict]],
        max_concurrency: Optional[int] = None,
        timeout: Optional[float] = None,
        raise_on_error: bool = False,
        **options
    ) -> List[Any]:
        """Perform multiple requests in parallel.

        Args:
            requests: List of (data, options) tuples
            max_concurrency: Maximum number of concurrent requests
            timeout: Optional timeout in seconds for the entire batch
            raise_on_error: Whether to raise on the first error
            **options: Additional options for all requests

        Returns:
            List of responses or exceptions

        Raises:
            TimeoutError: If the batch times out and raise_on_error is True
            PynectorError: For other errors if raise_on_error is True
        """
        results = [None] * len(requests)

        # Log batch request if logging is enabled
        if self._logger:
            self._logger.info(
                "batch_request.start",
                request_count=len(requests),
                max_concurrency=max_concurrency,
                timeout=timeout
            )

        # Create a capacity limiter if max_concurrency is specified
        limiter = anyio.CapacityLimiter(max_concurrency) if max_concurrency else None

        async def process_request(index, data, request_options):
            try:
                # Merge options
                merged_options = options.copy()
                merged_options.update(request_options)

                # Process with limiter if specified
                if limiter:
                    async with limiter:
                        result = await self.request(data, **merged_options)
                else:
                    result = await self.request(data, **merged_options)

                results[index] = result
            except Exception as e:
                results[index] = e
                if raise_on_error:
                    raise

        try:
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

            # Log completion if logging is enabled
            if self._logger:
                success_count = sum(1 for r in results if not isinstance(r, Exception))
                error_count = sum(1 for r in results if isinstance(r, Exception))
                self._logger.info(
                    "batch_request.complete",
                    request_count=len(requests),
                    success_count=success_count,
                    error_count=error_count
                )

            return results

        except anyio.TimeoutError:
            # Log timeout if logging is enabled
            if self._logger:
                self._logger.error(
                    "batch_request.timeout",
                    timeout=timeout,
                    request_count=len(requests)
                )

            if raise_on_error:
                raise TimeoutError(f"Batch request timed out after {timeout} seconds")

            # Fill remaining results with timeout errors
            for i, result in enumerate(results):
                if result is None:
                    results[i] = TimeoutError(f"Request timed out after {timeout} seconds")

            return results
```

### 5.7 Resource Management

```python
    async def aclose(self) -> None:
        """Close the Pynector instance and release resources."""
        if self._owns_transport and self._transport is not None:
            if self._logger:
                self._logger.info("client.closing")

            try:
                await self._transport.disconnect()
                if self._logger:
                    self._logger.info("client.closed")
            except Exception as e:
                if self._logger:
                    self._logger.error(
                        "client.close_error",
                        error=str(e),
                        error_type=type(e).__name__
                    )
                raise
            finally:
                self._transport = None
                self._transport_initialized = False

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
```

### 5.8 Retry Utility Method

```python
async def request_with_retry(
    self,
    data: Any,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    **options
) -> Any:
    """Send a request with retry for transient errors.

    Args:
        data: The data to send
        max_retries: The maximum number of retry attempts
        retry_delay: The initial delay between retries (will be exponentially increased)
        **options: Additional options for the request

    Returns:
        The response data

    Raises:
        TransportError: If all retry attempts fail
        TimeoutError: If the request times out after all retry attempts
        PynectorError: For other errors
    """
    last_error = None

    # Start span if tracing is enabled
    if self._tracer:
        with self._tracer.start_as_current_span("pynector.request_with_retry") as span:
            span.set_attribute("max_retries", max_retries)
            span.set_attribute("retry_delay", retry_delay)

            for attempt in range(max_retries):
                span.set_attribute("attempt", attempt + 1)

                try:
                    result = await self.request(data, **options)
                    span.set_attribute("successful_attempt", attempt + 1)
                    return result
                except TransportError as e:
                    last_error = e
                    span.record_exception(e)

                    if attempt < max_retries - 1:
                        # Calculate backoff delay
                        delay = retry_delay * (2 ** attempt)
                        span.set_attribute(f"retry_delay_{attempt}", delay)

                        # Wait before retrying
                        await anyio.sleep(delay)
                    else:
                        break

            # If we get here, all retries failed
            raise last_error
    else:
        # Non-traced version
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

        # If we get here, all retries failed
        raise last_error
```

## 6. Integration Points

### 6.1 Transport Integration

The `Pynector` class integrates with the Transport Abstraction Layer through:

1. **TransportFactory Registry**: Uses the registry to create transport
   instances
2. **Transport Protocol**: Interacts with transports through the
   `TransportProtocol` interface
3. **Resource Management**: Properly manages transport resources through async
   context managers

### 6.2 Concurrency Integration

The `Pynector` class integrates with Structured Concurrency through:

1. **Task Groups**: Uses AnyIO task groups for parallel request processing
2. **Timeouts**: Uses AnyIO's `fail_after` for timeout handling
3. **Capacity Limiters**: Uses AnyIO's `CapacityLimiter` for concurrency control

### 6.3 Observability Integration

The `Pynector` class integrates with Optional Observability through:

1. **Telemetry Facade**: Uses the `get_telemetry()` function to obtain tracer
   and logger
2. **Span Creation**: Creates spans for request and batch request operations
3. **Logging**: Logs key events with structured data
4. **Error Recording**: Records exceptions in spans and logs

## 7. Testing Strategy

The testing strategy for the `Pynector` class includes:

1. **Unit Tests**: Testing individual methods with mocked dependencies
2. **Integration Tests**: Testing the interaction with real transports
3. **Concurrency Tests**: Testing batch requests with different concurrency
   settings
4. **Error Handling Tests**: Testing error propagation and retry behavior
5. **Resource Management Tests**: Testing proper cleanup of resources

Detailed test cases are provided in the Test Implementation (TI) document.

## 8. Implementation Considerations

### 8.1 Performance Optimizations

1. **Lazy Initialization**: Transport instances are created and connected only
   when needed
2. **Connection Reuse**: Transport connections are reused across multiple
   requests
3. **Efficient Batch Processing**: Task groups and capacity limiters optimize
   parallel processing
4. **Telemetry Overhead**: Telemetry is optional and can be disabled for
   performance-critical applications

### 8.2 Error Handling

1. **Error Categorization**: Errors are categorized into transport errors,
   configuration errors, and timeout errors
2. **Error Propagation**: Errors from child tasks are properly propagated to the
   parent
3. **Retry Logic**: Transient errors can be handled with retry logic
4. **Logging**: Errors are logged with context information for debugging

### 8.3 Resource Management

1. **Async Context Management**: Resources are managed through async context
   managers
2. **Proper Cleanup**: Resources are properly cleaned up even when errors occur
3. **Ownership Tracking**: The class tracks whether it owns the transport to
   determine cleanup responsibility

## 9. References

1. Technical Design Specification: Core Pynector Class
   ([TDS-6.md](../tds/TDS-6.md)) (search: internal-document)
2. Technical Design Specification: Transport Abstraction Layer
   ([TDS-1.md](../tds/TDS-1.md)) (search: internal-document)
3. Technical Design Specification: Structured Concurrency
   ([TDS-2.md](../tds/TDS-2.md)) (search: internal-document)
4. Technical Design Specification: Optional Observability
   ([TDS-3.md](../tds/TDS-3.md)) (search: internal-document)
