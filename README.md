# Pynector

Pynector is a Python library that provides a flexible, maintainable, and
type-safe interface for network communication.

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

## Installation

```bash
pip install pynector
```

## License

This project is licensed under the terms of the MIT license.
