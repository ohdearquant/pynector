# Test Implementation: Core Pynector Class

**Issue:** #6\
**Author:** pynector-implementer\
**Date:** 2025-05-05\
**Status:** Draft

## 1. Introduction

This Test Implementation (TI) document outlines the testing strategy and
specific test cases for the core `Pynector` class as specified in
[TDS-6.md](../tds/TDS-6.md) and implemented according to
[IP-6.md](../ip/IP-6.md). The tests will verify that the implementation
correctly integrates the Transport Abstraction Layer, Structured Concurrency,
and Optional Observability components.

### 1.1 Purpose

The purpose of this test implementation plan is to:

- Define the testing approach and methodology
- Specify unit tests for each method of the `Pynector` class
- Outline integration tests for component interactions
- Define performance and concurrency tests

### 1.2 Scope

This test implementation plan covers:

- Unit tests for the `Pynector` class
- Integration tests with transport, concurrency, and telemetry components
- Error handling and edge case tests
- Resource management tests

## 2. Test File Structure

The tests for the core `Pynector` class will be organized in the following file
structure:

```
tests/
├── __init__.py
├── conftest.py                    # Common test fixtures
├── test_client.py                 # Unit tests for Pynector class
└── test_integration.py            # Integration tests
```

## 3. Test Fixtures

The following fixtures will be defined in `conftest.py` to support testing:

```python
# tests/conftest.py

import pytest
import anyio
from typing import Dict, Any, List, Optional, AsyncGenerator
from unittest.mock import MagicMock, AsyncMock

from pynector.transport.protocol import TransportProtocol
from pynector.transport.factory import TransportFactory, get_transport_factory_registry

# Mock Transport Protocol implementation
class MockTransport(TransportProtocol):
    """Mock transport for testing."""
    
    def __init__(self, responses=None, raise_on_connect=None, raise_on_send=None):
        self.responses = responses or [b"mock response"]
        self.raise_on_connect = raise_on_connect
        self.raise_on_send = raise_on_send
        self.connected = False
        self.sent_data = []
        self.connect_count = 0
        self.disconnect_count = 0
        self.send_count = 0
        
    async def connect(self) -> None:
        self.connect_count += 1
        if self.raise_on_connect:
            raise self.raise_on_connect
        self.connected = True
        
    async def disconnect(self) -> None:
        self.disconnect_count += 1
        self.connected = False
        
    async def send(self, message: Any, **options) -> None:
        self.send_count += 1
        if self.raise_on_send:
            raise self.raise_on_send
        self.sent_data.append((message, options))
        
    async def receive(self) -> AsyncGenerator[bytes, None]:
        for response in self.responses:
            yield response
            
    async def __aenter__(self) -> 'MockTransport':
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()

# Mock Transport Factory
class MockTransportFactory(TransportFactory):
    """Mock transport factory for testing."""
    
    def __init__(self, transport=None):
        self.transport = transport or MockTransport()
        self.create_count = 0
        
    def create_transport(self, **kwargs) -> TransportProtocol:
        self.create_count += 1
        self.last_kwargs = kwargs
        return self.transport

@pytest.fixture
def mock_transport():
    """Fixture providing a mock transport."""
    return MockTransport()

@pytest.fixture
def mock_transport_factory(mock_transport):
    """Fixture providing a mock transport factory."""
    return MockTransportFactory(mock_transport)

@pytest.fixture
def register_mock_transport_factory(mock_transport_factory):
    """Fixture that registers a mock transport factory."""
    registry = get_transport_factory_registry()
    registry.register("mock", mock_transport_factory)
    yield
    # Clean up
    if "mock" in registry._factories:
        del registry._factories["mock"]

# Mock Telemetry
@pytest.fixture
def mock_telemetry(monkeypatch):
    """Fixture providing mock telemetry components."""
    mock_tracer = MagicMock()
    mock_span = AsyncMock()
    mock_span.__enter__.return_value = mock_span
    mock_span.__aenter__.return_value = mock_span
    mock_tracer.start_as_current_span.return_value = mock_span
    mock_tracer.start_span.return_value = mock_span
    
    mock_logger = MagicMock()
    
    mock_get_telemetry = MagicMock(return_value=(mock_tracer, mock_logger))
    monkeypatch.setattr("pynector.client.get_telemetry", mock_get_telemetry)
    
    return mock_tracer, mock_logger

# Anyio Backend Selection
@pytest.fixture(params=["asyncio", "trio"])
def anyio_backend(request):
    """Fixture to run tests with different anyio backends."""
    return request.param
```

## 4. Unit Tests

### 4.1 Initialization Tests

```python
# tests/test_client.py
import pytest
import anyio
from unittest.mock import MagicMock, AsyncMock
from typing import Dict, Any, List, Optional

from pynector import Pynector
from pynector.errors import PynectorError, TransportError, ConfigurationError, TimeoutError

@pytest.mark.anyio
async def test_init_with_defaults():
    """Test initialization with default parameters."""
    client = Pynector()
    assert client._transport is None
    assert client._transport_type == "http"
    assert client._owns_transport is True
    assert client._config == {}

@pytest.mark.anyio
async def test_init_with_custom_config():
    """Test initialization with custom configuration."""
    config = {"timeout": 30.0, "retry_count": 3}
    client = Pynector(config=config)
    assert client._config == config
    assert client._get_config("timeout") == 30.0

@pytest.mark.anyio
async def test_init_with_transport():
    """Test initialization with a pre-configured transport."""
    transport = AsyncMock()
    client = Pynector(transport=transport)
    assert client._transport is transport
    assert client._owns_transport is False

@pytest.mark.anyio
async def test_init_with_invalid_transport_type(register_mock_transport_factory):
    """Test initialization with an invalid transport type."""
    with pytest.raises(ConfigurationError):
        Pynector(transport_type="invalid")
```

### 4.2 Configuration Tests

```python
@pytest.mark.anyio
async def test_get_config_from_instance():
    """Test getting configuration from instance config."""
    client = Pynector(config={"timeout": 30.0})
    assert client._get_config("timeout") == 30.0

@pytest.mark.anyio
async def test_get_config_from_env(monkeypatch):
    """Test getting configuration from environment variables."""
    monkeypatch.setenv("PYNECTOR_TIMEOUT", "45.0")
    client = Pynector()
    assert client._get_config("timeout") == "45.0"
    
    # Instance config should override environment
    client = Pynector(config={"timeout": 30.0})
    assert client._get_config("timeout") == 30.0
```

### 4.3 Transport Management Tests

```python
@pytest.mark.anyio
async def test_get_transport_creates_transport(register_mock_transport_factory):
    """Test that _get_transport creates a transport when needed."""
    client = Pynector(transport_type="mock")
    transport = await client._get_transport()
    assert transport is not None
    assert client._transport_initialized is True
    assert transport.connect_count == 1

@pytest.mark.anyio
async def test_get_transport_reuses_transport(register_mock_transport_factory):
    """Test that _get_transport reuses an existing transport."""
    client = Pynector(transport_type="mock")
    transport1 = await client._get_transport()
    transport2 = await client._get_transport()
    assert transport1 is transport2
    assert transport1.connect_count == 1  # Should only connect once

@pytest.mark.anyio
async def test_get_transport_with_connection_error(register_mock_transport_factory, mock_transport_factory):
    """Test _get_transport with a connection error."""
    mock_transport_factory.transport.raise_on_connect = ConnectionError("Connection failed")
    client = Pynector(transport_type="mock")
    with pytest.raises(TransportError):
        await client._get_transport()
```

### 4.4 Request Method Tests

```python
@pytest.mark.anyio
async def test_request_success(register_mock_transport_factory, mock_transport):
    """Test successful request."""
    mock_transport.responses = [b"test response"]
    client = Pynector(transport_type="mock")
    response = await client.request({"test": "data"})
    assert response == b"test response"
    assert mock_transport.send_count == 1
    assert mock_transport.sent_data[0][0] == {"test": "data"}

@pytest.mark.anyio
async def test_request_with_options(register_mock_transport_factory, mock_transport):
    """Test request with additional options."""
    client = Pynector(transport_type="mock")
    await client.request({"test": "data"}, headers={"X-Test": "value"})
    assert mock_transport.sent_data[0][1]["headers"] == {"X-Test": "value"}

@pytest.mark.anyio
async def test_request_with_timeout(register_mock_transport_factory, mock_transport):
    """Test request with timeout."""
    client = Pynector(transport_type="mock")
    
    # Mock a slow response that will trigger timeout
    async def slow_receive():
        await anyio.sleep(0.5)
        yield b"too late"
    
    mock_transport.receive = slow_receive
    
    with pytest.raises(TimeoutError):
        await client.request({"test": "data"}, timeout=0.1)

@pytest.mark.anyio
async def test_request_with_transport_error(register_mock_transport_factory, mock_transport):
    """Test request with transport error."""
    mock_transport.raise_on_send = ConnectionError("Send failed")
    client = Pynector(transport_type="mock")
    with pytest.raises(TransportError):
        await client.request({"test": "data"})

@pytest.mark.anyio
async def test_request_with_telemetry(register_mock_transport_factory, mock_telemetry):
    """Test request with telemetry."""
    mock_tracer, mock_logger = mock_telemetry
    client = Pynector(transport_type="mock")
    await client.request({"test": "data"})
    
    # Verify span was created
    assert mock_tracer.start_as_current_span.called
    assert mock_tracer.start_as_current_span.call_args[0][0] == "pynector.request"
    
    # Verify logging
    assert mock_logger.info.called
```

### 4.5 Batch Request Tests

```python
@pytest.mark.anyio
async def test_batch_request_success(register_mock_transport_factory, mock_transport):
    """Test successful batch request."""
    mock_transport.responses = [b"response 1", b"response 2", b"response 3"]
    client = Pynector(transport_type="mock")
    
    requests = [
        ({"id": 1}, {}),
        ({"id": 2}, {}),
        ({"id": 3}, {})
    ]
    
    responses = await client.batch_request(requests)
    assert len(responses) == 3
    assert all(not isinstance(r, Exception) for r in responses)
    assert mock_transport.send_count == 3

@pytest.mark.anyio
async def test_batch_request_with_max_concurrency(register_mock_transport_factory, mock_transport):
    """Test batch request with max concurrency."""
    client = Pynector(transport_type="mock")
    
    requests = [({"id": i}, {}) for i in range(10)]
    
    # With max_concurrency=2, requests should be processed in batches
    await client.batch_request(requests, max_concurrency=2)
    assert mock_transport.send_count == 10

@pytest.mark.anyio
async def test_batch_request_with_timeout(register_mock_transport_factory, mock_transport):
    """Test batch request with timeout."""
    client = Pynector(transport_type="mock")
    
    # Mock a slow response that will trigger timeout
    async def slow_receive():
        await anyio.sleep(0.5)
        yield b"too late"
    
    mock_transport.receive = slow_receive
    
    requests = [({"id": i}, {}) for i in range(5)]
    
    # Without raise_on_error, should return TimeoutError objects
    responses = await client.batch_request(requests, timeout=0.1)
    assert len(responses) == 5
    assert all(isinstance(r, TimeoutError) for r in responses)
    
    # With raise_on_error, should raise TimeoutError
    with pytest.raises(TimeoutError):
        await client.batch_request(requests, timeout=0.1, raise_on_error=True)

@pytest.mark.anyio
async def test_batch_request_with_partial_errors(register_mock_transport_factory, mock_transport_factory):
    """Test batch request with some requests failing."""
    # Create a transport that fails on specific requests
    class PartialFailTransport(MockTransport):
        async def send(self, message, **options):
            self.send_count += 1
            self.sent_data.append((message, options))
            if isinstance(message, dict) and message.get("id") == 2:
                raise ConnectionError("Failed for id 2")
    
    mock_transport_factory.transport = PartialFailTransport()
    client = Pynector(transport_type="mock")
    
    requests = [
        ({"id": 1}, {}),
        ({"id": 2}, {}),
        ({"id": 3}, {})
    ]
    
    # Without raise_on_error, should return mix of responses and exceptions
    responses = await client.batch_request(requests)
    assert len(responses) == 3
    assert not isinstance(responses[0], Exception)
    assert isinstance(responses[1], TransportError)
    assert not isinstance(responses[2], Exception)
```

### 4.6 Resource Management Tests

```python
@pytest.mark.anyio
async def test_aclose(register_mock_transport_factory, mock_transport):
    """Test aclose method."""
    client = Pynector(transport_type="mock")
    await client._get_transport()  # Initialize transport
    await client.aclose()
    assert mock_transport.disconnect_count == 1
    assert client._transport is None
    assert client._transport_initialized is False

@pytest.mark.anyio
async def test_aclose_with_external_transport(mock_transport):
    """Test aclose with external transport."""
    client = Pynector(transport=mock_transport)
    await client.aclose()
    # Should not disconnect external transport
    assert mock_transport.disconnect_count == 0

@pytest.mark.anyio
async def test_async_context_manager(register_mock_transport_factory, mock_transport):
    """Test async context manager protocol."""
    async with Pynector(transport_type="mock") as client:
        assert mock_transport.connect_count == 1
        await client.request({"test": "data"})
    
    # Should disconnect on exit
    assert mock_transport.disconnect_count == 1
```

### 4.7 Retry Utility Tests

```python
@pytest.mark.anyio
async def test_request_with_retry_success(register_mock_transport_factory, mock_transport):
    """Test request_with_retry with immediate success."""
    client = Pynector(transport_type="mock")
    response = await client.request_with_retry({"test": "data"})
    assert response == b"mock response"
    assert mock_transport.send_count == 1

@pytest.mark.anyio
async def test_request_with_retry_after_failure(register_mock_transport_factory, mock_transport_factory):
    """Test request_with_retry with success after failure."""
    # Create a transport that fails on first attempt
    class RetryTransport(MockTransport):
        def __init__(self):
            super().__init__()
            self.attempts = 0
            
        async def send(self, message, **options):
            self.send_count += 1
            self.sent_data.append((message, options))
            self.attempts += 1
            if self.attempts == 1:
                raise ConnectionError("First attempt fails")
    
    mock_transport_factory.transport = RetryTransport()
    client = Pynector(transport_type="mock")
    
    # Should succeed on second attempt
    response = await client.request_with_retry({"test": "data"}, retry_delay=0.01)
    assert response == b"mock response"
    assert mock_transport_factory.transport.send_count == 2

@pytest.mark.anyio
async def test_request_with_retry_max_retries(register_mock_transport_factory, mock_transport):
    """Test request_with_retry with max retries exceeded."""
    mock_transport.raise_on_send = ConnectionError("Always fails")
    client = Pynector(transport_type="mock")
    
    with pytest.raises(TransportError):
        await client.request_with_retry({"test": "data"}, max_retries=3, retry_delay=0.01)
    
    # Should have attempted 3 times
    assert mock_transport.send_count == 3
```

## 5. Integration Tests

```python
# tests/test_integration.py

import pytest
import anyio
from typing import Dict, Any, List, Optional

from pynector import Pynector
from pynector.errors import PynectorError, TransportError, TimeoutError

@pytest.mark.anyio
async def test_integration_with_http_transport():
    """Test integration with HTTP transport."""
    # Create a mock HTTP server
    from tests.transport.http.mock_server import MockHttpServer
    
    async with MockHttpServer() as server:
        # Create client with HTTP transport
        client = Pynector(
            transport_type="http",
            base_url=server.base_url,
            headers={"Content-Type": "application/json"}
        )
        
        # Configure server to return a specific response
        server.add_json_response("/test", {"result": "success"})
        
        # Make a request
        response = await client.request({"path": "/test", "method": "GET"})
        
        # Verify response
        assert isinstance(response, dict)
        assert response["result"] == "success"
        
        # Verify server received the request
        assert len(server.requests) == 1
        assert server.requests[0]["path"] == "/test"
        assert server.requests[0]["method"] == "GET"

@pytest.mark.anyio
async def test_integration_batch_request():
    """Test batch request with real concurrency."""
    # Create a mock HTTP server
    from tests.transport.http.mock_server import MockHttpServer
    
    async with MockHttpServer() as server:
        # Create client with HTTP transport
        client = Pynector(
            transport_type="http",
            base_url=server.base_url,
            headers={"Content-Type": "application/json"}
        )
        
        # Configure server to return different responses
        server.add_json_response("/1", {"id": 1})
        server.add_json_response("/2", {"id": 2})
        server.add_json_response("/3", {"id": 3})
        
        # Create batch request
        requests = [
            ({"path": "/1", "method": "GET"}, {}),
            ({"path": "/2", "method": "GET"}, {}),
            ({"path": "/3", "method": "GET"}, {})
        ]
        
        # Make batch request
        responses = await client.batch_request(requests, max_concurrency=2)
        
        # Verify responses
        assert len(responses) == 3
        assert all(not isinstance(r, Exception) for r in responses)
        assert responses[0]["id"] == 1
        assert responses[1]["id"] == 2
        assert responses[2]["id"] == 3
        
        # Verify server received all requests
        assert len(server.requests) == 3
        assert {req["path"] for req in server.requests} == {"/1", "/2", "/3"}

@pytest.mark.anyio
async def test_integration_with_telemetry():
    """Test integration with telemetry."""
    # Skip if OpenTelemetry is not available
    pytest.importorskip("opentelemetry")
    
    # Configure telemetry
    from pynector.telemetry import configure_telemetry
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
    
    # Set up a tracer provider with a simple processor
    tracer_provider = TracerProvider()
    span_processor = SimpleSpanProcessor(ConsoleSpanExporter())
    tracer_provider.add_span_processor(span_processor)
    trace.set_tracer_provider(tracer_provider)
    
    # Configure telemetry
    configure_telemetry(service_name="test-service")
    
    # Create a mock HTTP server
    from tests.transport.http.mock_server import MockHttpServer
    
    async with MockHttpServer() as server:
        # Create client with HTTP transport and telemetry
        client = Pynector(
            transport_type="http",
            base_url=server.base_url,
            enable_telemetry=True
        )
        
        # Configure server to return a response
        server.add_json_response("/test", {"result": "success"})
        
        # Make a request
        response = await client.request({"path": "/test", "method": "GET"})
        
        # Verify response
        assert response["result"] == "success"
```

## 6. Performance Tests

```python
@pytest.mark.anyio
@pytest.mark.performance
async def test_performance_batch_request():
    """Test performance of batch request with different concurrency limits."""
    # Create a mock HTTP server
    from tests.transport.http.mock_server import MockHttpServer
    import time
    
    async with MockHttpServer() as server:
        # Create client with HTTP transport
        client = Pynector(
            transport_type="http",
            base_url=server.base_url,
            headers={"Content-Type": "application/json"}
        )
        
        # Configure server to return a response with delay
        server.add_json_response("/test", {"result": "success"}, delay=0.01)
        
        # Create a large batch of requests
        requests = [({"path": "/test", "method": "GET"}, {}) for _ in range(50)]
        
        # Test with different concurrency limits
        concurrency_limits = [1, 5, 10, 20, 50]  # No limit = 50
        results = []
        
        for limit in concurrency_limits:
            start_time = time.time()
            await client.batch_request(requests, max_concurrency=limit)
            duration = time.time() - start_time
            results.append((limit, duration))
            
        # Verify that higher concurrency leads to faster execution
        # This is a simple check - in real tests we'd want more sophisticated analysis
        durations = [duration for _, duration in results]
        assert durations[0] > durations[-1]  # Sequential should be slower than parallel
```

## 7. Conclusion

This Test Implementation document outlines a comprehensive testing strategy for
the core `Pynector` class. The tests cover all aspects of the implementation,
from basic initialization to complex integration scenarios.

The key testing areas include:

1. **Initialization and Configuration**: Verifying that the `Pynector` class
   initializes correctly with different configuration options
2. **Transport Management**: Testing the creation, connection, and reuse of
   transports
3. **Request Handling**: Validating the core request functionality with various
   options and error conditions
4. **Batch Processing**: Ensuring that batch requests are properly parallelized
   and managed
5. **Resource Management**: Confirming that resources are properly acquired and
   released
6. **Observability Integration**: Checking that telemetry is correctly
   integrated when enabled
7. **Error Handling**: Verifying appropriate error propagation and handling

These tests will ensure that the implementation meets the requirements specified
in the Technical Design Specification and provides a reliable foundation for the
pynector library.
