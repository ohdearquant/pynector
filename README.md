# Pynector

Pynector is a Python library that provides a flexible, maintainable, and
type-safe interface for network communication with optional observability
features and structured concurrency.

## Core Pynector Client

The `Pynector` class is the main entry point for using the library. It
integrates the Transport Abstraction Layer, Structured Concurrency, and Optional
Observability components into a cohesive, user-friendly API.

### Key Features

- **Flexible Transport Integration**: Works with both built-in and custom
  transports
- **Efficient Batch Processing**: Parallel request processing with concurrency
  limits
- **Optional Observability**: Integrated tracing and logging with no-op
  fallbacks
- **Resource Safety**: Proper async resource management with context managers
- **Robust Error Handling**: Specific exception types and retry mechanisms

### Usage

```python
from pynector import Pynector

# Create a client with HTTP transport
async with Pynector(
    transport_type="http",
    base_url="https://api.example.com",
    headers={"Content-Type": "application/json"}
) as client:
    # Make a request
    response = await client.request({"path": "/users", "method": "GET"})

    # Make multiple requests in parallel
    requests = [
        ({"path": "/users/1", "method": "GET"}, {}),
        ({"path": "/users/2", "method": "GET"}, {}),
        ({"path": "/users/3", "method": "GET"}, {})
    ]
    responses = await client.batch_request(requests, max_concurrency=2)
```

For more detailed documentation, see the
[Core Client Documentation](docs/client.md).

## Structured Concurrency

The Structured Concurrency module is a core component of Pynector that provides
a robust foundation for managing concurrent operations in Python. It leverages
AnyIO to provide a consistent interface for structured concurrency across both
asyncio and trio backends.

### Key Features

- **Structured Concurrency Pattern**: Ensures that concurrent operations have
  well-defined lifetimes that are bound to a scope.
- **AnyIO Integration**: Provides a consistent interface for both asyncio and
  trio backends.
- **Task Groups**: Manage multiple concurrent tasks with proper cleanup and
  error propagation.
- **Cancellation Scopes**: Fine-grained control over task cancellation and
  timeouts.
- **Resource Management Primitives**: Synchronization mechanisms like locks,
  semaphores, and events.
- **Concurrency Patterns**: Common patterns like connection pools, parallel
  requests, and worker pools.

### Components

The Structured Concurrency module consists of the following components:

1. **Task Groups**: Provide a way to spawn and manage multiple concurrent tasks
   while ensuring proper cleanup and error propagation.

2. **Cancellation Scopes**: Provide fine-grained control over task cancellation
   and timeouts.

3. **Resource Management Primitives**: Implement synchronization mechanisms for
   coordinating access to shared resources.

4. **Error Handling**: Utilities for handling cancellation and shielding tasks
   from cancellation.

5. **Concurrency Patterns**: Implement common patterns like connection pools,
   parallel requests, and worker pools.

### Usage

Here's a simple example of how to use the Structured Concurrency module:

```python
import asyncio
from pynector.concurrency import create_task_group

async def task1():
    print("Task 1 started")
    await asyncio.sleep(1)
    print("Task 1 completed")

async def task2():
    print("Task 2 started")
    await asyncio.sleep(2)
    print("Task 2 completed")

async def main():
    async with create_task_group() as tg:
        await tg.start_soon(task1)
        await tg.start_soon(task2)
        print("All tasks started")

    print("All tasks completed")

asyncio.run(main())
```

For more detailed documentation, see the
[Structured Concurrency Documentation](docs/concurrency.md).

## Transport Abstraction Layer

The Transport Abstraction Layer is a core component of Pynector that provides a
flexible and maintainable interface for network communication. It follows the
sans-I/O pattern, which separates I/O concerns from protocol logic, making it
easier to test, maintain, and extend.

### Key Features

- **Protocol-Based Design**: Uses Python's Protocol classes for interface
  definitions, enabling static type checking.
- **Sans-I/O Pattern**: Separates I/O concerns from protocol logic for better
  testability and maintainability.
- **Async Context Management**: Proper implementation of async context managers
  for resource handling.
- **Comprehensive Error Hierarchy**: Well-structured error hierarchy with
  specific exception types.
- **Message Protocols**: Flexible message serialization and deserialization with
  support for different formats.
- **Factory Pattern**: Factory method pattern for creating transport instances.
- **HTTP Transport**: Complete HTTP client implementation using httpx with
  connection pooling, retry mechanism, and comprehensive error handling.
- **SDK Transport**: Unified interface for interacting with AI model provider
  SDKs (OpenAI and Anthropic) with adapter pattern, error translation, and
  streaming support.

### Components

The Transport Abstraction Layer consists of the following components:

1. **Transport Protocol**: Defines the interface for all transport
   implementations with async methods for connect, disconnect, send, and receive
   operations.

2. **Message Protocol**: Defines the interface for message serialization and
   deserialization.

3. **Error Hierarchy**: Implements a comprehensive error hierarchy for
   transport-related errors.

4. **Message Implementations**:
   - `JsonMessage`: Implements JSON serialization/deserialization.
   - `BinaryMessage`: Implements binary message format with headers and payload.
   - `HttpMessage`: Implements HTTP-specific message format with support for
     headers, query parameters, JSON data, form data, and file uploads.

5. **Transport Factory**: Implements the Factory Method pattern for creating
   transport instances.

6. **Transport Factory Registry**: Provides a registry for transport factories.

7. **HTTP Transport Implementation**:
   - `HTTPTransport`: Implements the Transport Protocol for HTTP communication
     using httpx.
   - `HTTPTransportFactory`: Creates and configures HTTP transport instances.
   - HTTP-specific error hierarchy for detailed error handling.

8. **SDK Transport Implementation**:
   - `SdkTransport`: Implements the Transport Protocol for AI model provider
     SDKs.
   - `SDKAdapter`: Abstract base class for SDK-specific adapters.
   - `OpenAIAdapter` and `AnthropicAdapter`: Concrete adapters for specific
     SDKs.
   - `SdkTransportFactory`: Creates and configures SDK transport instances.
   - SDK-specific error hierarchy for detailed error handling.

### Usage

Here's a simple example of how to use the Transport Abstraction Layer with the
HTTP transport:

```python
from pynector.transport import TransportFactoryRegistry
from pynector.transport.http import HttpMessage, HTTPTransportFactory

# Set up registry
registry = TransportFactoryRegistry()
registry.register(
    "http",
    HTTPTransportFactory(
        base_url="https://api.example.com",
        message_type=HttpMessage,
    ),
)

# Create a transport
transport = registry.create_transport("http")

# Use the transport with async context manager
async with transport as t:
    # Create a GET request message
    message = HttpMessage(
        method="GET",
        url="/users",
        params={"limit": 10},
    )

    # Send the message
    await t.send(message)

    # Receive the response
    async for response in t.receive():
        data = response.get_payload()["data"]
        print(f"Received {len(data)} users")
```

For more detailed documentation, see the
[Transport Abstraction Layer Documentation](docs/transport.md) and the
[HTTP Transport Documentation](docs/http_transport.md) or
[SDK Transport Documentation](docs/sdk_transport.md).

## Optional Observability

The Optional Observability module provides telemetry features for tracing and
logging with minimal dependencies. It follows a design that makes OpenTelemetry
and structlog optional dependencies with no-op fallbacks.

### Key Features

- **Optional Dependencies**: Works with or without OpenTelemetry and structlog.
- **No-op Fallbacks**: Graceful degradation when dependencies are not available.
- **Context Propagation**: Maintains trace context across async boundaries.
- **Flexible Configuration**: Configure via environment variables or API.
- **Unified API**: Consistent interface regardless of dependency availability.

### Components

1. **Telemetry Facade**: Unified interface for tracing and logging operations.
2. **No-op Implementations**: Fallbacks when dependencies are missing.
3. **Context Propagation**: Maintains trace context in async code.
4. **Configuration**: Flexible options for telemetry setup.
5. **Dependency Detection**: Auto-detects available dependencies.

### Usage

```python
from pynector.telemetry import get_telemetry, configure_telemetry

# Configure telemetry (optional)
configure_telemetry(service_name="my-service")

# Get tracer and logger
tracer, logger = get_telemetry("my_component")

# Use the logger
logger.info("Operation started", operation="process_data")

# Use the tracer
with tracer.start_as_current_span("process_data") as span:
    span.set_attribute("data.size", 100)
    logger.info("Processing data", items=100)
```

For more detailed documentation, see the
[Optional Observability Documentation](docs/observability.md).

## Installation

```bash
# Basic installation
pip install pynector

# With observability features
pip install pynector[observability]
```

## License

This project is licensed under the terms of the MIT license.
