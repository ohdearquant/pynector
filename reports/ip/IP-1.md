# Implementation Plan: Transport Abstraction Layer

**Issue:** #1\
**Author:** pynector-implementer\
**Date:** 2025-05-05\
**Status:** Draft

## 1. Introduction

This Implementation Plan (IP) outlines the approach for implementing the
Transport Abstraction Layer as specified in [TDS-1.md](../tds/TDS-1.md). The
implementation will follow the sans-I/O pattern, utilize Protocol classes for
interfaces, and implement async context management for resource handling.

## 2. Project Structure

The Transport Abstraction Layer will be implemented in the following directory
structure:

```
pynector/
├── transport/
│   ├── __init__.py
│   ├── protocol.py       # Transport and Message Protocol definitions
│   ├── errors.py         # Error hierarchy
│   ├── message/
│   │   ├── __init__.py
│   │   ├── json.py       # JsonMessage implementation
│   │   └── binary.py     # BinaryMessage implementation
│   ├── factory.py        # TransportFactory implementation
│   └── registry.py       # TransportFactoryRegistry implementation
└── tests/
    └── transport/
        ├── __init__.py
        ├── test_protocol.py
        ├── test_errors.py
        ├── test_message.py
        ├── test_factory.py
        └── test_registry.py
```

## 3. Implementation Details

### 3.1 Transport Protocol (`protocol.py`)

The `Transport` Protocol will be implemented as specified in TDS-1.md, defining
the interface for all transport implementations.

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

### 3.2 Message Protocol (`protocol.py`)

The `Message` Protocol will define the interface for message serialization and
deserialization.

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

### 3.3 Error Hierarchy (`errors.py`)

The error hierarchy will be implemented as specified in TDS-1.md, providing a
consistent approach to transport-specific errors.

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

### 3.4 Message Implementations

#### 3.4.1 JsonMessage (`message/json.py`)

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
        try:
            return json.dumps(data).encode('utf-8')
        except (TypeError, ValueError) as e:
            from pynector.transport.errors import SerializationError
            raise SerializationError(f"Failed to serialize JSON message: {e}")
        
    @classmethod
    def deserialize(cls, data: bytes) -> 'JsonMessage':
        try:
            parsed = json.loads(data.decode('utf-8'))
            return cls(
                headers=parsed.get("headers", {}),
                payload=parsed.get("payload", None)
            )
        except json.JSONDecodeError as e:
            from pynector.transport.errors import DeserializationError
            raise DeserializationError(f"Invalid JSON data: {e}")
            
    def get_headers(self) -> Dict[str, Any]:
        return self.headers
        
    def get_payload(self) -> Any:
        return self.payload
```

#### 3.4.2 BinaryMessage (`message/binary.py`)

```python
from typing import Dict, Any, ClassVar, Optional

class BinaryMessage:
    """Binary message implementation."""
    
    content_type: ClassVar[str] = "application/octet-stream"
    
    def __init__(self, headers: Dict[str, Any], payload: bytes):
        self.headers = headers
        self.payload = payload
        
    def serialize(self) -> bytes:
        # Simple format: 4-byte header length + header JSON + payload
        import json
        from pynector.transport.errors import SerializationError
        
        try:
            header_json = json.dumps(self.headers).encode('utf-8')
            header_len = len(header_json)
            return header_len.to_bytes(4, byteorder='big') + header_json + self.payload
        except (TypeError, ValueError) as e:
            raise SerializationError(f"Failed to serialize binary message: {e}")
        
    @classmethod
    def deserialize(cls, data: bytes) -> 'BinaryMessage':
        import json
        from pynector.transport.errors import DeserializationError
        
        try:
            if len(data) < 4:
                raise DeserializationError("Message too short")
                
            header_len = int.from_bytes(data[:4], byteorder='big')
            if len(data) < 4 + header_len:
                raise DeserializationError("Message truncated")
                
            header_json = data[4:4+header_len]
            headers = json.loads(header_json.decode('utf-8'))
            payload = data[4+header_len:]
            
            return cls(headers=headers, payload=payload)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise DeserializationError(f"Invalid binary message format: {e}")
            
    def get_headers(self) -> Dict[str, Any]:
        return self.headers
        
    def get_payload(self) -> bytes:
        return self.payload
```

### 3.5 TransportFactory (`factory.py`)

The `TransportFactory` will be implemented as specified in TDS-1.md, following
the Factory Method pattern.

```python
from typing import Protocol, Dict, Any, TypeVar, Type, Generic

T = TypeVar('T')

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

### 3.6 TransportFactoryRegistry (`registry.py`)

The `TransportFactoryRegistry` will be implemented as specified in TDS-1.md,
providing a registry for transport factories.

```python
from typing import Dict, Any
from pynector.transport.protocol import Transport
from pynector.transport.factory import TransportFactory

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

## 4. Implementation Approach

The implementation will follow these steps:

1. **Set up project structure:** Create the necessary directories and files
2. **Implement core protocols:** Implement the `Transport` and `Message`
   protocols
3. **Implement error hierarchy:** Implement the error classes
4. **Implement message types:** Implement the `JsonMessage` and `BinaryMessage`
   classes
5. **Implement factory and registry:** Implement the `TransportFactory` protocol
   and `TransportFactoryRegistry` class
6. **Write tests:** Write comprehensive tests for all components
7. **Documentation:** Add docstrings and type hints to all components

## 5. Dependencies

The implementation will require the following dependencies:

- Python 3.9 or higher (as specified in pyproject.toml)
- Standard library modules:
  - `typing` for Protocol classes and type hints
  - `json` for JSON serialization/deserialization
  - `contextlib` for async context management
  - `asyncio` for async/await support

No external dependencies are required for the core implementation.

## 6. Testing Strategy

The testing strategy is detailed in the Test Implementation document (TI-1.md).
It will include:

- Unit tests for all components
- Integration tests for component interactions
- Property-based tests for message serialization/deserialization
- Mock transports for testing without I/O

## 7. References

1. Technical Design Specification: Transport Abstraction Layer (TDS-1.md)
   (search: internal-document)
2. Research Report: Transport Abstraction Layers in Python (RR-1.md) (search:
   internal-document)
3. Brett Cannon, "Network protocols, sans I/O" (search:
   exa-snarky.ca/network-protocols-sans-i-o)
4. Sans-I/O Documentation (search: exa-sans-io.readthedocs.io)
5. Real Python, "Python Protocols: Leveraging Structural Subtyping" (search:
   exa-realpython.com/python-protocol)
6. PEP 544 – Protocols: Structural subtyping (static duck typing) (search:
   exa-peps.python.org/pep-0544)
