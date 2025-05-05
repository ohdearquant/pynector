# Test Implementation: Transport Abstraction Layer

**Issue:** #1\
**Author:** pynector-implementer\
**Date:** 2025-05-05\
**Status:** Draft

## 1. Introduction

This Test Implementation (TI) document outlines the testing strategy for the
Transport Abstraction Layer as specified in [TDS-1.md](../tds/TDS-1.md) and
implemented according to [IP-1.md](../ip/IP-1.md). The testing approach follows
Test-Driven Development (TDD) principles and aims to achieve >80% code coverage.

## 2. Test Structure

The tests will be organized in the following directory structure:

```
tests/
└── transport/
    ├── __init__.py
    ├── test_protocol.py     # Tests for Transport and Message protocols
    ├── test_errors.py       # Tests for error hierarchy
    ├── test_message/
    │   ├── __init__.py
    │   ├── test_json.py     # Tests for JsonMessage
    │   └── test_binary.py   # Tests for BinaryMessage
    ├── test_factory.py      # Tests for TransportFactory
    └── test_registry.py     # Tests for TransportFactoryRegistry
```

## 3. Testing Framework and Tools

The tests will use the following tools:

- **pytest**: Primary testing framework
- **pytest-asyncio**: For testing async code
- **pytest-cov**: For measuring code coverage
- **hypothesis**: For property-based testing

## 4. Test Cases

### 4.1 Protocol Tests (`test_protocol.py`)

These tests will verify that the Protocol classes are correctly defined and can
be used for type checking.

#### 4.1.1 Transport Protocol Tests

```python
import pytest
from typing import AsyncIterator, Protocol, runtime_checkable
import inspect
from pynector.transport.protocol import Transport

def test_transport_protocol_methods():
    """Test that Transport protocol has all required methods."""
    assert hasattr(Transport, 'connect')
    assert hasattr(Transport, 'disconnect')
    assert hasattr(Transport, 'send')
    assert hasattr(Transport, 'receive')
    assert hasattr(Transport, '__aenter__')
    assert hasattr(Transport, '__aexit__')
    
    # Check method signatures
    assert inspect.iscoroutinefunction(Transport.connect)
    assert inspect.iscoroutinefunction(Transport.disconnect)
    assert inspect.iscoroutinefunction(Transport.send)
    assert inspect.iscoroutinefunction(Transport.__aenter__)
    assert inspect.iscoroutinefunction(Transport.__aexit__)
    
    # Check return type annotations
    assert Transport.connect.__annotations__.get('return') == None
    assert Transport.disconnect.__annotations__.get('return') == None
    assert Transport.send.__annotations__.get('return') == None
    # receive should return an AsyncIterator
    assert 'AsyncIterator' in str(Transport.receive.__annotations__.get('return'))

# Create a mock implementation to test runtime compatibility
class MockTransport:
    async def connect(self) -> None:
        pass
        
    async def disconnect(self) -> None:
        pass
        
    async def send(self, message) -> None:
        pass
        
    async def receive(self):
        yield b"test"
        
    async def __aenter__(self):
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()

@pytest.mark.asyncio
async def test_transport_implementation():
    """Test that a concrete implementation works with the protocol."""
    transport = MockTransport()
    
    # Test async context manager
    async with transport as t:
        await t.send("test")
        messages = [msg async for msg in t.receive()]
        assert messages == [b"test"]
```

#### 4.1.2 Message Protocol Tests

```python
from pynector.transport.protocol import Message

def test_message_protocol_methods():
    """Test that Message protocol has all required methods."""
    assert hasattr(Message, 'serialize')
    assert hasattr(Message, 'deserialize')
    assert hasattr(Message, 'get_headers')
    assert hasattr(Message, 'get_payload')
    
    # Check method signatures
    assert not inspect.iscoroutinefunction(Message.serialize)
    assert not inspect.iscoroutinefunction(Message.deserialize)
    assert not inspect.iscoroutinefunction(Message.get_headers)
    assert not inspect.iscoroutinefunction(Message.get_payload)
    
    # Check return type annotations
    assert Message.serialize.__annotations__.get('return') == bytes
    assert 'Dict' in str(Message.get_headers.__annotations__.get('return'))

# Create a mock implementation to test compatibility
class MockMessage:
    def __init__(self, headers, payload):
        self.headers = headers
        self.payload = payload
        
    def serialize(self) -> bytes:
        return b"test"
        
    @classmethod
    def deserialize(cls, data: bytes) -> 'MockMessage':
        return cls({}, "test")
        
    def get_headers(self):
        return self.headers
        
    def get_payload(self):
        return self.payload

def test_message_implementation():
    """Test that a concrete implementation works with the protocol."""
    message = MockMessage({"content-type": "text/plain"}, "Hello, world!")
    
    assert message.serialize() == b"test"
    assert message.get_headers() == {"content-type": "text/plain"}
    assert message.get_payload() == "Hello, world!"
    
    deserialized = MockMessage.deserialize(b"test")
    assert isinstance(deserialized, MockMessage)
```

### 4.2 Error Tests (`test_errors.py`)

These tests will verify that the error hierarchy is correctly implemented.

```python
import pytest
from pynector.transport.errors import (
    TransportError,
    ConnectionError,
    ConnectionTimeoutError,
    ConnectionRefusedError,
    MessageError,
    SerializationError,
    DeserializationError,
    TransportSpecificError
)

def test_error_hierarchy():
    """Test that the error hierarchy is correctly implemented."""
    # Test inheritance
    assert issubclass(ConnectionError, TransportError)
    assert issubclass(ConnectionTimeoutError, ConnectionError)
    assert issubclass(ConnectionRefusedError, ConnectionError)
    assert issubclass(MessageError, TransportError)
    assert issubclass(SerializationError, MessageError)
    assert issubclass(DeserializationError, MessageError)
    assert issubclass(TransportSpecificError, TransportError)
    
    # Test instantiation
    error = TransportError("Test error")
    assert str(error) == "Test error"
    
    # Test specific error types
    timeout_error = ConnectionTimeoutError("Connection timed out")
    assert isinstance(timeout_error, ConnectionError)
    assert isinstance(timeout_error, TransportError)
    assert str(timeout_error) == "Connection timed out"

def test_error_handling():
    """Test error handling in a typical use case."""
    try:
        raise ConnectionTimeoutError("Connection timed out after 30s")
    except ConnectionError as e:
        assert "timed out" in str(e)
    except TransportError:
        pytest.fail("ConnectionTimeoutError should be caught by ConnectionError")
        
    try:
        raise SerializationError("Failed to serialize message")
    except MessageError as e:
        assert "serialize" in str(e)
    except TransportError:
        pytest.fail("SerializationError should be caught by MessageError")
```

### 4.3 Message Tests

#### 4.3.1 JsonMessage Tests (`test_message/test_json.py`)

```python
import pytest
import json
from pynector.transport.message.json import JsonMessage
from pynector.transport.errors import SerializationError, DeserializationError

def test_json_message_init():
    """Test JsonMessage initialization."""
    headers = {"content-type": "application/json"}
    payload = {"name": "test", "value": 123}
    
    message = JsonMessage(headers, payload)
    
    assert message.headers == headers
    assert message.payload == payload
    assert message.content_type == "application/json"

def test_json_message_serialize():
    """Test JsonMessage serialization."""
    headers = {"content-type": "application/json"}
    payload = {"name": "test", "value": 123}
    
    message = JsonMessage(headers, payload)
    serialized = message.serialize()
    
    # Verify it's bytes
    assert isinstance(serialized, bytes)
    
    # Verify content
    deserialized = json.loads(serialized.decode('utf-8'))
    assert deserialized["headers"] == headers
    assert deserialized["payload"] == payload

def test_json_message_deserialize():
    """Test JsonMessage deserialization."""
    headers = {"content-type": "application/json"}
    payload = {"name": "test", "value": 123}
    data = json.dumps({"headers": headers, "payload": payload}).encode('utf-8')
    
    message = JsonMessage.deserialize(data)
    
    assert message.headers == headers
    assert message.payload == payload

def test_json_message_serialize_error():
    """Test JsonMessage serialization error."""
    # Create a message with non-serializable content
    headers = {"content-type": "application/json"}
    payload = {"circular": None}
    payload["circular"] = payload  # Create circular reference
    
    message = JsonMessage(headers, payload)
    
    with pytest.raises(SerializationError):
        message.serialize()

def test_json_message_deserialize_error():
    """Test JsonMessage deserialization error."""
    # Invalid JSON data
    data = b"not valid json"
    
    with pytest.raises(DeserializationError):
        JsonMessage.deserialize(data)

def test_json_message_get_methods():
    """Test JsonMessage get_headers and get_payload methods."""
    headers = {"content-type": "application/json"}
    payload = {"name": "test", "value": 123}
    
    message = JsonMessage(headers, payload)
    
    assert message.get_headers() == headers
    assert message.get_payload() == payload
```

#### 4.3.2 BinaryMessage Tests (`test_message/test_binary.py`)

```python
import pytest
import json
from pynector.transport.message.binary import BinaryMessage
from pynector.transport.errors import SerializationError, DeserializationError

def test_binary_message_init():
    """Test BinaryMessage initialization."""
    headers = {"content-type": "application/octet-stream"}
    payload = b"binary data"
    
    message = BinaryMessage(headers, payload)
    
    assert message.headers == headers
    assert message.payload == payload
    assert message.content_type == "application/octet-stream"

def test_binary_message_serialize():
    """Test BinaryMessage serialization."""
    headers = {"content-type": "application/octet-stream"}
    payload = b"binary data"
    
    message = BinaryMessage(headers, payload)
    serialized = message.serialize()
    
    # Verify it's bytes
    assert isinstance(serialized, bytes)
    
    # Verify format: 4-byte header length + header JSON + payload
    header_len = int.from_bytes(serialized[:4], byteorder='big')
    header_json = serialized[4:4+header_len]
    message_payload = serialized[4+header_len:]
    
    deserialized_headers = json.loads(header_json.decode('utf-8'))
    assert deserialized_headers == headers
    assert message_payload == payload

def test_binary_message_deserialize():
    """Test BinaryMessage deserialization."""
    headers = {"content-type": "application/octet-stream"}
    payload = b"binary data"
    
    # Create serialized data
    header_json = json.dumps(headers).encode('utf-8')
    header_len = len(header_json)
    data = header_len.to_bytes(4, byteorder='big') + header_json + payload
    
    message = BinaryMessage.deserialize(data)
    
    assert message.headers == headers
    assert message.payload == payload

def test_binary_message_serialize_error():
    """Test BinaryMessage serialization error."""
    # Create a message with non-serializable headers
    headers = {"circular": None}
    headers["circular"] = headers  # Create circular reference
    payload = b"binary data"
    
    message = BinaryMessage(headers, payload)
    
    with pytest.raises(SerializationError):
        message.serialize()

def test_binary_message_deserialize_error():
    """Test BinaryMessage deserialization error."""
    # Test cases for deserialization errors
    
    # 1. Message too short
    with pytest.raises(DeserializationError, match="too short"):
        BinaryMessage.deserialize(b"123")
        
    # 2. Message truncated
    header_len = (1000).to_bytes(4, byteorder='big')
    with pytest.raises(DeserializationError, match="truncated"):
        BinaryMessage.deserialize(header_len + b"short")
        
    # 3. Invalid header JSON
    header_len = (5).to_bytes(4, byteorder='big')
    with pytest.raises(DeserializationError, match="Invalid"):
        BinaryMessage.deserialize(header_len + b"not{json" + b"payload")

def test_binary_message_get_methods():
    """Test BinaryMessage get_headers and get_payload methods."""
    headers = {"content-type": "application/octet-stream"}
    payload = b"binary data"
    
    message = BinaryMessage(headers, payload)
    
    assert message.get_headers() == headers
    assert message.get_payload() == payload
```

### 4.4 Factory Tests (`test_factory.py`)

```python
import pytest
from typing import Any, Dict
from pynector.transport.factory import TransportFactory
from pynector.transport.protocol import Transport

# Create a mock transport for testing
class MockTransport:
    def __init__(self, host: str, port: int, **kwargs):
        self.host = host
        self.port = port
        self.options = kwargs
        
    async def connect(self) -> None:
        pass
        
    async def disconnect(self) -> None:
        pass
        
    async def send(self, message) -> None:
        pass
        
    async def receive(self):
        yield b"test"
        
    async def __aenter__(self):
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()

# Create a mock factory for testing
class MockTransportFactory:
    def __init__(self, default_host: str = "localhost"):
        self.default_host = default_host
        
    def create_transport(self, **kwargs: Any) -> MockTransport:
        host = kwargs.get("host", self.default_host)
        port = kwargs.get("port")
        
        if port is None:
            raise ValueError("Port is required")
            
        return MockTransport(host, port, **kwargs)

def test_factory_protocol():
    """Test that the TransportFactory protocol is correctly defined."""
    assert hasattr(TransportFactory, 'create_transport')

def test_mock_factory_implementation():
    """Test that a concrete factory implementation works."""
    factory = MockTransportFactory()
    
    # Test with valid arguments
    transport = factory.create_transport(port=8080)
    assert isinstance(transport, MockTransport)
    assert transport.host == "localhost"
    assert transport.port == 8080
    
    # Test with custom host
    transport = factory.create_transport(host="example.com", port=8080)
    assert transport.host == "example.com"
    
    # Test with missing required argument
    with pytest.raises(ValueError):
        factory.create_transport()
        
    # Test with additional arguments
    transport = factory.create_transport(port=8080, timeout=30)
    assert transport.options.get("timeout") == 30
```

### 4.5 Registry Tests (`test_registry.py`)

```python
import pytest
from pynector.transport.registry import TransportFactoryRegistry
from pynector.transport.factory import TransportFactory

# Create mock factories for testing
class MockHttpTransportFactory:
    def create_transport(self, **kwargs):
        return "http_transport"

class MockWebSocketTransportFactory:
    def create_transport(self, **kwargs):
        return "websocket_transport"

def test_registry_init():
    """Test TransportFactoryRegistry initialization."""
    registry = TransportFactoryRegistry()
    assert registry._factories == {}

def test_registry_register():
    """Test registering factories."""
    registry = TransportFactoryRegistry()
    
    http_factory = MockHttpTransportFactory()
    ws_factory = MockWebSocketTransportFactory()
    
    registry.register("http", http_factory)
    registry.register("websocket", ws_factory)
    
    assert "http" in registry._factories
    assert "websocket" in registry._factories
    assert registry._factories["http"] is http_factory
    assert registry._factories["websocket"] is ws_factory

def test_registry_get():
    """Test getting factories by name."""
    registry = TransportFactoryRegistry()
    
    http_factory = MockHttpTransportFactory()
    registry.register("http", http_factory)
    
    retrieved = registry.get("http")
    assert retrieved is http_factory
    
    # Test getting non-existent factory
    with pytest.raises(KeyError):
        registry.get("nonexistent")

def test_registry_create_transport():
    """Test creating transports through the registry."""
    registry = TransportFactoryRegistry()
    
    http_factory = MockHttpTransportFactory()
    ws_factory = MockWebSocketTransportFactory()
    
    registry.register("http", http_factory)
    registry.register("websocket", ws_factory)
    
    http_transport = registry.create_transport("http", host="example.com")
    assert http_transport == "http_transport"
    
    ws_transport = registry.create_transport("websocket", url="ws://example.com")
    assert ws_transport == "websocket_transport"
    
    # Test creating with non-existent factory
    with pytest.raises(KeyError):
        registry.create_transport("nonexistent")
```

### 4.6 Integration Tests

```python
import pytest
import asyncio
from pynector.transport.protocol import Transport, Message
from pynector.transport.message.json import JsonMessage
from pynector.transport.registry import TransportFactoryRegistry

# Create a mock transport implementation for testing
class MockJsonTransport:
    def __init__(self, messages=None):
        self.connected = False
        self.sent_messages = []
        self.receive_messages = messages or []
        
    async def connect(self) -> None:
        self.connected = True
        
    async def disconnect(self) -> None:
        self.connected = False
        
    async def send(self, message: JsonMessage) -> None:
        if not self.connected:
            raise ConnectionError("Not connected")
        self.sent_messages.append(message)
        
    async def receive(self):
        if not self.connected:
            raise ConnectionError("Not connected")
        for message in self.receive_messages:
            yield message
            
    async def __aenter__(self):
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()

class MockJsonTransportFactory:
    def create_transport(self, **kwargs):
        messages = kwargs.get("messages", [])
        return MockJsonTransport(messages)

@pytest.mark.asyncio
async def test_transport_integration():
    """Test the integration of transport components."""
    # Set up registry
    registry = TransportFactoryRegistry()
    registry.register("json", MockJsonTransportFactory())
    
    # Create messages
    message1 = JsonMessage({"id": "1"}, {"data": "test1"})
    message2 = JsonMessage({"id": "2"}, {"data": "test2"})
    
    # Create transport with pre-configured receive messages
    transport = registry.create_transport("json", messages=[message1, message2])
    
    # Test async context manager
    async with transport as t:
        # Test sending
        await t.send(JsonMessage({"id": "3"}, {"data": "test3"}))
        assert len(t.sent_messages) == 1
        assert t.sent_messages[0].get_payload()["data"] == "test3"
        
        # Test receiving
        received = [msg async for msg in t.receive()]
        assert len(received) == 2
        assert received[0].get_payload()["data"] == "test1"
        assert received[1].get_payload()["data"] == "test2"
    
    # Verify disconnected after context exit
    assert not transport.connected
```

### 4.7 Property-Based Tests

```python
import pytest
from hypothesis import given, strategies as st
from pynector.transport.message.json import JsonMessage
from pynector.transport.message.binary import BinaryMessage

@given(
    headers=st.dictionaries(
        keys=st.text(),
        values=st.one_of(st.text(), st.integers(), st.booleans())
    ),
    payload=st.one_of(
        st.dictionaries(
            keys=st.text(),
            values=st.one_of(st.text(), st.integers(), st.booleans())
        ),
        st.lists(st.one_of(st.text(), st.integers(), st.booleans())),
        st.text(),
        st.integers(),
        st.booleans()
    )
)
def test_json_message_roundtrip(headers, payload):
    """Test that JsonMessage serialization/deserialization roundtrip works."""
    message = JsonMessage(headers, payload)
    serialized = message.serialize()
    deserialized = JsonMessage.deserialize(serialized)
    
    assert deserialized.get_headers() == headers
    assert deserialized.get_payload() == payload

@given(
    headers=st.dictionaries(
        keys=st.text(),
        values=st.one_of(st.text(), st.integers(), st.booleans())
    ),
    payload=st.binary(min_size=0, max_size=1000)
)
def test_binary_message_roundtrip(headers, payload):
    """Test that BinaryMessage serialization/deserialization roundtrip works."""
    message = BinaryMessage(headers, payload)
    serialized = message.serialize()
    deserialized = BinaryMessage.deserialize(serialized)
    
    assert deserialized.get_headers() == headers
    assert deserialized.get_payload() == payload
```

## 5. Test Coverage

The tests are designed to achieve >80% code coverage across all components.
Coverage will be measured using pytest-cov and reported during CI runs.

```bash
pytest --cov=pynector.transport tests/transport/
```

## 6. Test Execution

Tests will be executed as part of the CI pipeline and can also be run locally
using pytest:

```bash
# Run all tests
pytest tests/transport/

# Run specific test file
pytest tests/transport/test_message/test_json.py

# Run with coverage
pytest --cov=pynector.transport tests/transport/

# Generate coverage report
pytest --cov=pynector.transport --cov-report=html tests/transport/
```

## 7. References

1. Technical Design Specification: Transport Abstraction Layer (TDS-1.md)
   (search: internal-document)
2. Implementation Plan: Transport Abstraction Layer (IP-1.md) (search:
   internal-document)
3. pytest Documentation (search: exa-docs.pytest.org)
4. pytest-asyncio Documentation (search: exa-pytest-asyncio.readthedocs.io)
5. hypothesis Documentation (search: exa-hypothesis.readthedocs.io)
6. Real Python, "Python Testing with pytest" (search:
   exa-realpython.com/python-testing-with-pytest)
