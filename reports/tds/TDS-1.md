# Technical Design Specification: Transport Abstraction Layer

**Issue:** #1\
**Author:** pynector-architect\
**Date:** 2025-05-05\
**Status:** Draft

## 1. Introduction

This Technical Design Specification (TDS) defines the architecture and
implementation details for the Transport Abstraction Layer in the pynector
project. The design is based on the research findings documented in
[RR-1.md](../rr/RR-1.md) and additional research.

### 1.1 Purpose

The Transport Abstraction Layer provides a flexible, maintainable, and type-safe
interface for network communication that:

- Separates protocol logic from I/O operations (sans-I/O pattern)
- Works with both synchronous and asynchronous code
- Enables testing without mocking I/O
- Facilitates reuse across different I/O frameworks

### 1.2 Scope

This specification covers:

- The `Transport` Protocol definition
- Message formats (Request/Response)
- Error handling strategy
- The `TransportFactory` design

### 1.3 Design Principles

The design adheres to the following principles:

1. **Separation of concerns:** Protocol implementation is completely separate
   from I/O operations
2. **Framework agnosticism:** Protocol libraries work with any I/O framework
   (sync or async)
3. **Direct byte manipulation:** Protocol code operates directly on bytes or
   text, not on I/O abstractions
4. **Type safety:** Leveraging Python's type system through Protocol classes
5. **Resource management:** Using async context managers for clean resource
   acquisition and release

## 2. Architecture Overview

The Transport Abstraction Layer consists of the following components:

1. **Transport Protocol:** Defines the interface for transport implementations
2. **Message Protocol:** Defines the interface for message
   serialization/deserialization
3. **Error Handling:** Defines a consistent approach to transport-specific
   errors
4. **TransportFactory:** Creates and configures transport instances

### 2.1 Component Diagram

```
┌─────────────────────────────────────┐
│           Client Application        │
└───────────────┬─────────────────────┘
                │
                ▼
┌─────────────────────────────────────┐
│         TransportFactory            │
└───────────────┬─────────────────────┘
                │ creates
                ▼
┌─────────────────────────────────────┐
│     Transport (Protocol)            │
├─────────────────────────────────────┤
│  - connect()                        │
│  - disconnect()                     │
│  - send(message)                    │
│  - receive() -> AsyncIterator       │
└───────────────┬─────────────────────┘
                │ uses
                ▼
┌─────────────────────────────────────┐
│     Message (Protocol)              │
├─────────────────────────────────────┤
│  - serialize() -> bytes             │
│  - deserialize(bytes) -> Message    │
└─────────────────────────────────────┘
```

## 3. Transport Protocol

The `Transport` Protocol defines the interface that all transport
implementations must satisfy. It is designed to be used with async context
management.

### 3.1 Interface Definition

```python
from typing import Protocol, AsyncIterator, Optional, Dict, Any, TypeVar, Generic
from contextlib import asynccontextmanager

T = TypeVar('T')

class Transport(Protocol, Generic[T]):
    """Protocol defining the interface for transport implementations."""

    async def connect(self) -> None:
        """Establish the connection to the remote endpoint.

        Raises:
            ConnectionError: If the connection cannot be established.
            TimeoutError: If the connection attempt times out.
        """
        ...

    async def disconnect(self) -> None:
        """Close the connection to the remote endpoint.

        This method should be idempotent and safe to call multiple times.
        """
        ...

    async def send(self, message: T) -> None:
        """Send a message over the transport.

        Args:
            message: The message to send.

        Raises:
            ConnectionError: If the connection is closed or broken.
            TransportError: For other transport-specific errors.
        """
        ...

    async def receive(self) -> AsyncIterator[T]:
        """Receive messages from the transport.

        Returns:
            An async iterator yielding messages as they are received.

        Raises:
            ConnectionError: If the connection is closed or broken.
            TransportError: For other transport-specific errors.
        """
        ...

    async def __aenter__(self) -> 'Transport[T]':
        """Enter the async context, establishing the connection.

        Returns:
            The transport instance.

        Raises:
            ConnectionError: If the connection cannot be established.
            TimeoutError: If the connection attempt times out.
        """
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the async context, closing the connection."""
        await self.disconnect()
```

### 3.2 Usage Example

```python
async def example_usage(transport: Transport[Message], message: Message):
    async with transport as t:
        await t.send(message)
        async for response in t.receive():
            process_response(response)
```

## 4. Message Protocol

The `Message` Protocol defines the interface for message serialization and
deserialization. This allows different message formats to be used with the same
transport.

### 4.1 Interface Definition

```python
from typing import Protocol, ClassVar, Dict, Any, Type, TypeVar

T = TypeVar('T', bound='Message')

class Message(Protocol):
    """Protocol defining the interface for message serialization/deserialization."""

    def serialize(self) -> bytes:
        """Convert the message to bytes for transmission.

        Returns:
            The serialized message as bytes.
        """
        ...

    @classmethod
    def deserialize(cls: Type[T], data: bytes) -> T:
        """Create a message from received bytes.

        Args:
            data: The serialized message as bytes.

        Returns:
            The deserialized message.

        Raises:
            ValueError: If the data cannot be deserialized.
        """
        ...

    def get_headers(self) -> Dict[str, Any]:
        """Get the message headers.

        Returns:
            A dictionary of header name to header value.
        """
        ...

    def get_payload(self) -> Any:
        """Get the message payload.

        Returns:
            The message payload.
        """
        ...
```

### 4.2 Concrete Message Types

The following concrete message types will be implemented:

1. **JsonMessage:** JSON-serialized messages
2. **BinaryMessage:** Raw binary messages
3. **ProtobufMessage:** Protocol Buffer messages (optional, for future
   expansion)

### 4.3 Example Implementation

```python
import json
from typing import Dict, Any, ClassVar, Type

class JsonMessage:
    """JSON-serialized message implementation."""

    content_type: ClassVar[str] = "application/json"

    def __init__(self, headers: Dict[str, Any], payload: Any):
        self.headers = headers
        self.payload = payload

    def serialize(self) -> bytes:
        data = {
            "headers": self.headers,
            "payload": self.payload
        }
        return json.dumps(data).encode('utf-8')

    @classmethod
    def deserialize(cls, data: bytes) -> 'JsonMessage':
        try:
            parsed = json.loads(data.decode('utf-8'))
            return cls(
                headers=parsed.get("headers", {}),
                payload=parsed.get("payload", None)
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON data: {e}")

    def get_headers(self) -> Dict[str, Any]:
        return self.headers

    def get_payload(self) -> Any:
        return self.payload
```

## 5. Error Handling

The error handling strategy is designed to provide a consistent approach to
transport-specific errors while allowing for specialized error types for
different transport implementations.

### 5.1 Error Hierarchy

```
Exception
└── TransportError
    ├── ConnectionError
    │   ├── ConnectionTimeoutError
    │   └── ConnectionRefusedError
    ├── MessageError
    │   ├── SerializationError
    │   └── DeserializationError
    └── TransportSpecificError (base for transport-specific errors)
        ├── HttpTransportError
        ├── WebSocketTransportError
        └── ...
```

### 5.2 Error Definitions

```python
class TransportError(Exception):
    """Base class for all transport-related errors."""
    pass

class ConnectionError(TransportError):
    """Error indicating a connection problem."""
    pass

class ConnectionTimeoutError(ConnectionError):
    """Error indicating a connection timeout."""
    pass

class ConnectionRefusedError(ConnectionError):
    """Error indicating a connection was refused."""
    pass

class MessageError(TransportError):
    """Error related to message handling."""
    pass

class SerializationError(MessageError):
    """Error during message serialization."""
    pass

class DeserializationError(MessageError):
    """Error during message deserialization."""
    pass

class TransportSpecificError(TransportError):
    """Base class for transport-specific errors."""
    pass
```

### 5.3 Error Handling Strategy

1. **Categorization:** Errors are categorized into connection errors, message
   errors, and transport-specific errors.
2. **Recovery:** Connection errors may be recoverable through retries with
   exponential backoff.
3. **Propagation:** Errors are propagated to the caller for handling at the
   appropriate level.
4. **Context:** Error messages include context information to aid in debugging.

### 5.4 Example Error Handling

```python
async def send_with_retry(transport: Transport[Message], message: Message, max_retries: int = 3):
    """Send a message with retry logic for connection errors."""
    for attempt in range(max_retries):
        try:
            await transport.send(message)
            return
        except ConnectionError as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

## 6. TransportFactory

The `TransportFactory` is responsible for creating and configuring transport
instances. It follows the Factory Method pattern to allow for different
transport implementations.

### 6.1 Interface Definition

```python
from typing import Protocol, Dict, Any, TypeVar, Type, Generic

T = TypeVar('T', bound='Transport')

class TransportFactory(Protocol, Generic[T]):
    """Protocol defining the interface for transport factories."""

    def create_transport(self, **kwargs: Any) -> T:
        """Create a new transport instance.

        Args:
            **kwargs: Transport-specific configuration options.

        Returns:
            A new transport instance.

        Raises:
            ValueError: If the configuration is invalid.
        """
        ...
```

### 6.2 Concrete Factory Implementations

The following concrete factory implementations will be provided:

1. **HttpTransportFactory:** Creates HTTP transport instances
2. **WebSocketTransportFactory:** Creates WebSocket transport instances
3. **MockTransportFactory:** Creates mock transport instances for testing

### 6.3 Example Implementation

```python
from typing import Dict, Any, Optional

class HttpTransportFactory:
    """Factory for creating HTTP transport instances."""

    def __init__(self, base_url: str, default_headers: Optional[Dict[str, str]] = None):
        self.base_url = base_url
        self.default_headers = default_headers or {}

    def create_transport(self, **kwargs: Any) -> 'HttpTransport':
        """Create a new HTTP transport instance.

        Args:
            **kwargs: HTTP transport configuration options.
                - timeout: Optional[float] - Request timeout in seconds
                - headers: Optional[Dict[str, str]] - Additional headers to include

        Returns:
            A new HTTP transport instance.
        """
        timeout = kwargs.get('timeout', 30.0)
        headers = {**self.default_headers, **(kwargs.get('headers', {}))}

        return HttpTransport(
            base_url=self.base_url,
            timeout=timeout,
            headers=headers
        )
```

### 6.4 Factory Registry

A registry will be provided to allow for dynamic registration and lookup of
transport factories:

```python
class TransportFactoryRegistry:
    """Registry for transport factories."""

    def __init__(self):
        self._factories = {}

    def register(self, name: str, factory: TransportFactory) -> None:
        """Register a transport factory.

        Args:
            name: The name to register the factory under.
            factory: The factory instance.
        """
        self._factories[name] = factory

    def get(self, name: str) -> TransportFactory:
        """Get a transport factory by name.

        Args:
            name: The name of the factory to get.

        Returns:
            The factory instance.

        Raises:
            KeyError: If no factory is registered with the given name.
        """
        return self._factories[name]

    def create_transport(self, name: str, **kwargs: Any) -> Transport:
        """Create a transport using a registered factory.

        Args:
            name: The name of the factory to use.
            **kwargs: Transport-specific configuration options.

        Returns:
            A new transport instance.

        Raises:
            KeyError: If no factory is registered with the given name.
        """
        factory = self.get(name)
        return factory.create_transport(**kwargs)
```

## 7. Implementation Considerations

### 7.1 Sans-I/O Compliance

To ensure compliance with the sans-I/O pattern:

1. **Separation of concerns:** Protocol logic is completely separate from I/O
   operations.
2. **Framework agnosticism:** The design works with any I/O framework (sync or
   async).
3. **Direct byte manipulation:** Protocol code operates directly on bytes or
   text, not on I/O abstractions.

### 7.2 Async Context Management

All transport implementations must support async context management through the
`__aenter__` and `__aexit__` methods. This ensures proper resource management
and cleanup.

### 7.3 Type Safety

The design leverages Python's type system through Protocol classes to provide
static type checking without requiring inheritance.

### 7.4 Testing

The design facilitates testing through:

1. **Mock transports:** Implementations that simulate network communication for
   testing.
2. **In-memory transports:** Implementations that operate entirely in memory for
   testing.
3. **Transport factories:** Factories that can be easily mocked or replaced for
   testing.

### 7.5 Performance Considerations

To ensure good performance:

1. **Buffer management:** Implementations should use efficient buffer management
   to minimize memory usage.
2. **Backpressure:** Implementations should handle backpressure to prevent
   memory exhaustion.
3. **Batching:** Implementations may batch messages to reduce overhead.

## 8. Future Considerations

The following areas are identified for future expansion:

1. **Additional transport types:** Support for additional transport types (e.g.,
   MQTT, gRPC).
2. **Multiplexing:** Support for multiplexing multiple logical connections over
   a single transport.
3. **Compression:** Support for message compression.
4. **Encryption:** Support for transport-level encryption.
5. **Authentication:** Support for transport-level authentication.

## 9. References

1. Research Report: Transport Abstraction Layers in Python (RR-1.md) (search:
   internal-document)
2. Brett Cannon, "Network protocols, sans I/O" (search:
   exa-snarky.ca/network-protocols-sans-i-o)
3. Sans-I/O Documentation (search: exa-sans-io.readthedocs.io)
4. Real Python, "Python Protocols: Leveraging Structural Subtyping" (search:
   exa-realpython.com/python-protocol)
5. PEP 544 – Protocols: Structural subtyping (static duck typing) (search:
   exa-peps.python.org/pep-0544)
6. Mypy Documentation, "Protocols and structural subtyping" (search:
   exa-mypy.readthedocs.io/en/stable/protocols.html)
7. Real Python, "Asynchronous context manager" (search:
   exa-realpython.com/ref/glossary/asynchronous-context-manager)
8. Shashi Kant, "Async with in Python" (search:
   exa-medium.com/@shashikantrbl123/async-with-in-python-deb0e62693cc)
9. Auth0 Blog, "Protocol Types in Python 3.8" (search:
   exa-auth0.com/blog/protocol-types-in-python)
10. Brett Cannon, "Designing an async API, from sans-I/O on up" (search:
    exa-snarky.ca/designing-an-async-api-from-sans-i-o-on-up)
11. Factory Method Pattern (search:
    exa-refactoring.guru/design-patterns/factory-method)
12. Railway Oriented Programming for Error Handling (search:
    exa-returns.readthedocs.io/en/latest/pages/railway.html)
