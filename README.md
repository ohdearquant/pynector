# Pynector

Pynector is a Python library that provides a flexible, maintainable, and
type-safe interface for network communication with optional observability features.

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

5. **Transport Factory**: Implements the Factory Method pattern for creating
   transport instances.

6. **Transport Factory Registry**: Provides a registry for transport factories.

### Usage

Here's a simple example of how to use the Transport Abstraction Layer:

```python
from pynector.transport import TransportFactoryRegistry
from pynector.transport.message import JsonMessage

# Set up registry
registry = TransportFactoryRegistry()
registry.register("my_transport", MyTransportFactory())

# Create a transport
transport = registry.create_transport("my_transport", host="example.com", port=8080)

# Use the transport with async context manager
async with transport as t:
    # Send a message
    await t.send(JsonMessage({"content-type": "application/json"}, {"data": "Hello, World!"}))

    # Receive messages
    async for message in t.receive():
        print(f"Received: {message.get_payload()}")
```

For more detailed documentation, see the
[Transport Abstraction Layer Documentation](docs/transport.md).

## Optional Observability

The Optional Observability module provides telemetry features for tracing and logging with minimal dependencies. It follows a design that makes OpenTelemetry and structlog optional dependencies with no-op fallbacks.

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
