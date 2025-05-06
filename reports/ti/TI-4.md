# Test Implementation: HTTP Transport

**Issue:** #4\
**Author:** pynector-implementer\
**Date:** 2025-05-05\
**Status:** Draft

## 1. Introduction

This Test Implementation (TI) document outlines the testing strategy for the
HTTP Transport component as specified in [TDS-4.md](../tds/TDS-4.md) and planned
in [IP-4.md](../ip/IP-4.md). The testing approach follows test-driven
development (TDD) principles, ensuring comprehensive test coverage for all
functionality.

## 2. Testing Strategy

The testing strategy consists of the following levels:

1. **Unit Tests:** Test individual components in isolation
2. **Integration Tests:** Test interactions between components
3. **Property Tests:** Test invariants and properties of the implementation
4. **Mock Tests:** Test with mocked HTTP responses

## 3. Test Structure

```
tests/transport/
├── http/
│   ├── __init__.py
│   ├── test_transport.py (Unit tests for HTTPTransport)
│   ├── test_factory.py (Unit tests for HTTPTransportFactory)
│   ├── test_errors.py (Unit tests for HTTP error classes)
│   ├── test_message.py (Unit tests for HttpMessage)
│   ├── test_integration.py (Integration tests)
│   └── test_property.py (Property-based tests)
└── test_integration.py (existing, to be extended)
```

## 4. Test Cases

### 4.1 Unit Tests for HTTPTransport

#### 4.1.1 Constructor Tests

```python
# Pseudocode for constructor tests
def test_http_transport_init_default_values():
    """Test HTTPTransport initialization with default values."""
    transport = HTTPTransport()
    assert transport.base_url == ""
    assert transport.headers == {}
    assert isinstance(transport.timeout, (float, httpx.Timeout))
    assert transport.max_retries == 3
    assert transport.retry_backoff_factor == 0.5
    assert transport.retry_status_codes == {429, 500, 502, 503, 504}
    assert transport.follow_redirects is True
    assert transport.verify_ssl is True
    assert transport.http2 is False
    assert transport._client is None
    assert transport._message_type is None

def test_http_transport_init_custom_values():
    """Test HTTPTransport initialization with custom values."""
    transport = HTTPTransport(
        base_url="https://example.com",
        headers={"User-Agent": "pynector/1.0"},
        timeout=5.0,
        max_retries=2,
        retry_backoff_factor=1.0,
        retry_status_codes={500, 502},
        follow_redirects=False,
        verify_ssl=False,
        http2=True,
    )
    assert transport.base_url == "https://example.com"
    assert transport.headers == {"User-Agent": "pynector/1.0"}
    assert transport.timeout == 5.0
    assert transport.max_retries == 2
    assert transport.retry_backoff_factor == 1.0
    assert transport.retry_status_codes == {500, 502}
    assert transport.follow_redirects is False
    assert transport.verify_ssl is False
    assert transport.http2 is True
```

#### 4.1.2 Connection Management Tests

```python
# Pseudocode for connection management tests
@pytest.mark.asyncio
async def test_connect():
    """Test connect method creates AsyncClient."""
    transport = HTTPTransport()
    await transport.connect()
    assert transport._client is not None
    assert isinstance(transport._client, httpx.AsyncClient)
    await transport.disconnect()

@pytest.mark.asyncio
async def test_disconnect():
    """Test disconnect method closes AsyncClient."""
    transport = HTTPTransport()
    await transport.connect()
    client = transport._client
    await transport.disconnect()
    assert transport._client is None
    # Verify client was closed (mock or spy)

@pytest.mark.asyncio
async def test_connect_error():
    """Test connect method handles errors."""
    with patch("httpx.AsyncClient", side_effect=httpx.ConnectError("Connection error")):
        transport = HTTPTransport()
        with pytest.raises(ConnectionError):
            await transport.connect()

@pytest.mark.asyncio
async def test_connect_timeout():
    """Test connect method handles timeouts."""
    with patch("httpx.AsyncClient", side_effect=httpx.ConnectTimeout("Connection timeout")):
        transport = HTTPTransport()
        with pytest.raises(ConnectionTimeoutError):
            await transport.connect()

@pytest.mark.asyncio
async def test_context_manager():
    """Test async context manager protocol."""
    async with HTTPTransport() as transport:
        assert transport._client is not None
        assert isinstance(transport._client, httpx.AsyncClient)
    assert transport._client is None
```

#### 4.1.3 Send Method Tests

```python
# Pseudocode for send method tests
@pytest.mark.asyncio
async def test_send_basic():
    """Test basic send functionality."""
    transport = HTTPTransport()
    message = HttpMessage(method="GET", url="/test")
    
    # Mock the AsyncClient.request method
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    
    with patch.object(httpx.AsyncClient, "request", return_value=mock_response):
        await transport.connect()
        await transport.send(message)
        # Verify request was called with correct parameters

@pytest.mark.asyncio
async def test_send_not_connected():
    """Test send when not connected raises ConnectionError."""
    transport = HTTPTransport()
    message = HttpMessage(method="GET", url="/test")
    
    with pytest.raises(ConnectionError, match="Transport not connected"):
        await transport.send(message)

@pytest.mark.asyncio
async def test_send_retry_success():
    """Test send with retry logic (success after retry)."""
    transport = HTTPTransport(max_retries=2)
    message = HttpMessage(method="GET", url="/test")
    
    # First request fails with 503, second succeeds with 200
    mock_response_fail = MagicMock(spec=httpx.Response)
    mock_response_fail.status_code = 503
    
    mock_response_success = MagicMock(spec=httpx.Response)
    mock_response_success.status_code = 200
    
    with patch.object(httpx.AsyncClient, "request", side_effect=[mock_response_fail, mock_response_success]):
        await transport.connect()
        await transport.send(message)
        # Verify request was called twice

@pytest.mark.asyncio
async def test_send_retry_max_exceeded():
    """Test send with retry logic (max retries exceeded)."""
    transport = HTTPTransport(max_retries=2)
    message = HttpMessage(method="GET", url="/test")
    
    # All requests fail with 503
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 503
    mock_response.reason_phrase = "Service Unavailable"
    
    with patch.object(httpx.AsyncClient, "request", return_value=mock_response):
        await transport.connect()
        with pytest.raises(HTTPServerError):
            await transport.send(message)
        # Verify request was called 3 times (initial + 2 retries)

@pytest.mark.asyncio
async def test_send_network_error_retry():
    """Test send with network error retry."""
    transport = HTTPTransport(max_retries=2)
    message = HttpMessage(method="GET", url="/test")
    
    # First request fails with ConnectError, second succeeds
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    
    with patch.object(httpx.AsyncClient, "request", side_effect=[httpx.ConnectError("Connection error"), mock_response]):
        await transport.connect()
        await transport.send(message)
        # Verify request was called twice
```

#### 4.1.4 Receive Method Tests

```python
# Pseudocode for receive method tests
@pytest.mark.asyncio
async def test_receive_basic():
    """Test basic receive functionality."""
    transport = HTTPTransport()
    transport._message_type = HttpMessage
    
    # Mock _get_next_response to return a valid response
    mock_response = b'{"headers": {}, "payload": {"data": "test"}}'
    with patch.object(HTTPTransport, "_get_next_response", return_value=mock_response):
        await transport.connect()
        async for message in transport.receive():
            assert isinstance(message, HttpMessage)
            assert message.get_payload()["data"] == "test"
            break  # Only expect one message

@pytest.mark.asyncio
async def test_receive_not_connected():
    """Test receive when not connected raises ConnectionError."""
    transport = HTTPTransport()
    
    with pytest.raises(ConnectionError, match="Transport not connected"):
        async for _ in transport.receive():
            pass

@pytest.mark.asyncio
async def test_receive_no_message_type():
    """Test receive with no message type set."""
    transport = HTTPTransport()
    await transport.connect()
    
    with pytest.raises(HTTPTransportError, match="No message type has been set"):
        async for _ in transport.receive():
            pass

@pytest.mark.asyncio
async def test_receive_deserialization_error():
    """Test receive with deserialization error."""
    transport = HTTPTransport()
    transport._message_type = HttpMessage
    
    # Mock _get_next_response to return invalid data
    with patch.object(HTTPTransport, "_get_next_response", return_value=b'invalid json'):
        await transport.connect()
        with pytest.raises(MessageError):
            async for _ in transport.receive():
                pass
```

#### 4.1.5 Helper Method Tests

```python
# Pseudocode for helper method tests
def test_extract_headers():
    """Test _extract_headers method."""
    transport = HTTPTransport(headers={"User-Agent": "pynector/1.0"})
    message = HttpMessage(headers={"Content-Type": "application/json", "X-Test": "test"})
    
    headers = transport._extract_headers(message)
    assert headers["User-Agent"] == "pynector/1.0"
    assert headers["Content-Type"] == "application/json"
    assert headers["X-Test"] == "test"

def test_prepare_request():
    """Test _prepare_request method."""
    transport = HTTPTransport()
    message = HttpMessage(
        method="POST",
        url="/test",
        params={"q": "test"},
        json_data={"data": "test"}
    )
    
    method, url, request_kwargs = transport._prepare_request(message)
    assert method == "POST"
    assert url == "/test"
    assert request_kwargs["params"] == {"q": "test"}
    assert request_kwargs["json"] == {"data": "test"}

def test_handle_error_response():
    """Test _handle_error_response method."""
    transport = HTTPTransport()
    
    # Test various status codes
    for status_code, error_class in [
        (401, HTTPUnauthorizedError),
        (403, HTTPForbiddenError),
        (404, HTTPNotFoundError),
        (408, HTTPTimeoutError),
        (429, HTTPTooManyRequestsError),
        (400, HTTPClientError),
        (500, HTTPServerError),
    ]:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = status_code
        mock_response.reason_phrase = "Test"
        
        with pytest.raises(error_class):
            transport._handle_error_response(mock_response)
```

### 4.2 Unit Tests for HttpMessage

```python
# Pseudocode for HttpMessage tests
def test_http_message_init():
    """Test HttpMessage initialization."""
    message = HttpMessage(
        method="GET",
        url="/test",
        headers={"X-Test": "test"},
        params={"q": "test"},
        json_data={"data": "test"}
    )
    assert message.headers == {"X-Test": "test"}
    assert message.payload["method"] == "GET"
    assert message.payload["url"] == "/test"
    assert message.payload["params"] == {"q": "test"}
    assert message.payload["json"] == {"data": "test"}

def test_http_message_serialize():
    """Test HttpMessage serialization."""
    message = HttpMessage(
        method="GET",
        url="/test",
        headers={"X-Test": "test"},
        params={"q": "test"}
    )
    data = message.serialize()
    assert isinstance(data, bytes)
    parsed = json.loads(data.decode("utf-8"))
    assert parsed["headers"] == {"X-Test": "test"}
    assert parsed["payload"]["method"] == "GET"
    assert parsed["payload"]["url"] == "/test"
    assert parsed["payload"]["params"] == {"q": "test"}

def test_http_message_deserialize():
    """Test HttpMessage deserialization."""
    data = json.dumps({
        "headers": {"X-Test": "test"},
        "payload": {
            "method": "GET",
            "url": "/test",
            "params": {"q": "test"}
        }
    }).encode("utf-8")
    
    message = HttpMessage.deserialize(data)
    assert message.headers == {"X-Test": "test"}
    assert message.payload["method"] == "GET"
    assert message.payload["url"] == "/test"
    assert message.payload["params"] == {"q": "test"}

def test_http_message_deserialize_invalid():
    """Test HttpMessage deserialization with invalid data."""
    with pytest.raises(ValueError):
        HttpMessage.deserialize(b"invalid json")

def test_http_message_get_headers():
    """Test HttpMessage.get_headers method."""
    message = HttpMessage(headers={"X-Test": "test"})
    assert message.get_headers() == {"X-Test": "test"}

def test_http_message_get_payload():
    """Test HttpMessage.get_payload method."""
    message = HttpMessage(method="GET", url="/test")
    payload = message.get_payload()
    assert payload["method"] == "GET"
    assert payload["url"] == "/test"
```

### 4.3 Unit Tests for HTTPTransportFactory

```python
# Pseudocode for HTTPTransportFactory tests
def test_http_transport_factory_init():
    """Test HTTPTransportFactory initialization."""
    factory = HTTPTransportFactory(
        base_url="https://example.com",
        message_type=HttpMessage,
        default_headers={"User-Agent": "pynector/1.0"}
    )
    assert factory.base_url == "https://example.com"
    assert factory.message_type == HttpMessage
    assert factory.default_headers == {"User-Agent": "pynector/1.0"}
    assert factory.default_timeout == 30.0
    assert factory.default_max_retries == 3
    assert factory.default_retry_backoff_factor == 0.5
    assert factory.default_retry_status_codes == {429, 500, 502, 503, 504}
    assert factory.default_follow_redirects is True
    assert factory.default_verify_ssl is True
    assert factory.default_http2 is False

def test_create_transport_default():
    """Test create_transport with default options."""
    factory = HTTPTransportFactory(
        base_url="https://example.com",
        message_type=HttpMessage
    )
    transport = factory.create_transport()
    assert transport.base_url == "https://example.com"
    assert transport._message_type == HttpMessage
    assert transport.headers == {}
    assert transport.timeout == 30.0
    assert transport.max_retries == 3
    assert transport.retry_backoff_factor == 0.5
    assert transport.retry_status_codes == {429, 500, 502, 503, 504}
    assert transport.follow_redirects is True
    assert transport.verify_ssl is True
    assert transport.http2 is False

def test_create_transport_custom():
    """Test create_transport with custom options."""
    factory = HTTPTransportFactory(
        base_url="https://example.com",
        message_type=HttpMessage,
        default_headers={"User-Agent": "pynector/1.0"}
    )
    transport = factory.create_transport(
        headers={"X-Test": "test"},
        timeout=5.0,
        max_retries=2,
        retry_backoff_factor=1.0,
        retry_status_codes={500, 502},
        follow_redirects=False,
        verify_ssl=False,
        http2=True
    )
    assert transport.base_url == "https://example.com"
    assert transport._message_type == HttpMessage
    assert transport.headers == {"User-Agent": "pynector/1.0", "X-Test": "test"}
    assert transport.timeout == 5.0
    assert transport.max_retries == 2
    assert transport.retry_backoff_factor == 1.0
    assert transport.retry_status_codes == {500, 502}
    assert transport.follow_redirects is False
    assert transport.verify_ssl is False
    assert transport.http2 is True
```

### 4.4 Integration Tests

```python
# Pseudocode for integration tests
@pytest.mark.asyncio
async def test_http_transport_with_registry():
    """Test HTTPTransport with TransportFactoryRegistry."""
    registry = TransportFactoryRegistry()
    factory = HTTPTransportFactory(
        base_url="https://example.com",
        message_type=HttpMessage
    )
    registry.register("http", factory)
    
    transport = registry.create_transport("http")
    assert isinstance(transport, HTTPTransport)
    assert transport.base_url == "https://example.com"
    assert transport._message_type == HttpMessage

@pytest.mark.asyncio
async def test_http_transport_end_to_end():
    """Test HTTPTransport end-to-end with mock server."""
    # Set up mock server
    async with MockHTTPServer() as server:
        server.add_route("/test", lambda: {"data": "test"}, status_code=200)
        
        # Create transport
        transport = HTTPTransport(base_url=server.url)
        message = HttpMessage(method="GET", url="/test")
        
        # Send and receive
        async with transport:
            await transport.send(message)
            async for response in transport.receive():
                assert response.get_payload()["data"] == "test"
                break

@pytest.mark.asyncio
async def test_http_transport_streaming():
    """Test HTTPTransport streaming with mock server."""
    # Set up mock server
    async with MockHTTPServer() as server:
        server.add_streaming_route("/stream", ["chunk1", "chunk2", "chunk3"])
        
        # Create transport
        transport = HTTPTransport(base_url=server.url)
        message = HttpMessage(method="GET", url="/stream")
        
        # Stream response
        chunks = []
        async with transport:
            async for chunk in transport.stream_response(message):
                chunks.append(chunk)
        
        assert len(chunks) == 3
        assert b"".join(chunks).decode("utf-8") == "chunk1chunk2chunk3"
```

### 4.5 Property Tests

```python
# Pseudocode for property tests
@given(
    method=st.sampled_from(["GET", "POST", "PUT", "DELETE", "PATCH"]),
    url=st.text(min_size=1),
    params=st.dictionaries(st.text(), st.text()),
    json_data=st.dictionaries(st.text(), st.text())
)
def test_http_message_roundtrip(method, url, params, json_data):
    """Test HttpMessage serialization/deserialization roundtrip."""
    message = HttpMessage(
        method=method,
        url=url,
        params=params,
        json_data=json_data
    )
    data = message.serialize()
    deserialized = HttpMessage.deserialize(data)
    
    assert deserialized.payload["method"] == message.payload["method"]
    assert deserialized.payload["url"] == message.payload["url"]
    assert deserialized.payload["params"] == message.payload["params"]
    assert deserialized.payload["json"] == message.payload["json"]

@given(
    base_url=st.text(),
    headers=st.dictionaries(st.text(), st.text()),
    timeout=st.floats(min_value=0.1, max_value=60.0),
    max_retries=st.integers(min_value=0, max_value=10),
    retry_backoff_factor=st.floats(min_value=0.1, max_value=5.0)
)
def test_http_transport_factory_properties(base_url, headers, timeout, max_retries, retry_backoff_factor):
    """Test HTTPTransportFactory properties."""
    factory = HTTPTransportFactory(
        base_url=base_url,
        message_type=HttpMessage,
        default_headers=headers,
        default_timeout=timeout,
        default_max_retries=max_retries,
        default_retry_backoff_factor=retry_backoff_factor
    )
    
    transport = factory.create_transport()
    
    assert transport.base_url == base_url
    assert transport.headers == headers
    assert transport.timeout == timeout
    assert transport.max_retries == max_retries
    assert transport.retry_backoff_factor == retry_backoff_factor
```

## 5. Mock Server for Testing

To facilitate testing without relying on external services, we will implement a
simple mock HTTP server:

```python
# Pseudocode for MockHTTPServer
class MockHTTPServer:
    """Mock HTTP server for testing."""
    
    def __init__(self):
        self.app = web.Application()
        self.routes = {}
        self.server = None
        self.url = None
    
    async def __aenter__(self):
        """Start the server."""
        # Set up routes
        for path, (handler, status_code) in self.routes.items():
            self.app.router.add_get(path, self._create_handler(handler, status_code))
        
        # Start the server
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "localhost", 0)
        await self.site.start()
        
        # Get the server URL
        self.url = f"http://localhost:{self.site._server.sockets[0].getsockname()[1]}"
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Stop the server."""
        await self.runner.cleanup()
    
    def add_route(self, path, handler, status_code=200):
        """Add a route to the server."""
        self.routes[path] = (handler, status_code)
    
    def add_streaming_route(self, path, chunks):
        """Add a streaming route to the server."""
        async def streaming_handler(request):
            response = web.StreamResponse()
            await response.prepare(request)
            for chunk in chunks:
                await response.write(chunk.encode("utf-8"))
                await asyncio.sleep(0.01)
            return response
        
        self.app.router.add_get(path, streaming_handler)
    
    def _create_handler(self, handler, status_code):
        """Create a request handler."""
        async def request_handler(request):
            result = handler() if callable(handler) else handler
            return web.json_response(result, status=status_code)
        
        return request_handler
```

## 6. Test Implementation Plan

### 6.1 Phase 1: Setup (Day 1)

1. Create the test directory structure
2. Implement basic test fixtures
3. Implement MockHTTPServer for testing

### 6.2 Phase 2: Unit Tests (Days 2-3)

1. Implement unit tests for HttpMessage
2. Implement unit tests for HTTPTransport constructor and connection management
3. Implement unit tests for HTTPTransport helper methods
4. Implement unit tests for HTTPTransportFactory

### 6.3 Phase 3: Integration Tests (Day 4)

1. Implement integration tests for HTTPTransport with TransportFactoryRegistry
2. Implement end-to-end tests with MockHTTPServer

### 6.4 Phase 4: Advanced Tests (Day 5)

1. Implement tests for streaming support
2. Implement tests for circuit breaker pattern
3. Implement tests for custom response handlers

### 6.5 Phase 5: Property Tests (Day 6)

1. Implement property tests for HttpMessage
2. Implement property tests for HTTPTransportFactory
3. Implement property tests for HTTPTransport

## 7. Test Coverage Goals

The test suite should achieve the following coverage goals:

1. **Line Coverage:** >90% for all modules
2. **Branch Coverage:** >85% for all modules
3. **Function Coverage:** 100% for public API

## 8. Conclusion

This test implementation plan provides a comprehensive approach to testing the
HTTP Transport component. By following this plan, we will ensure that the
implementation is robust, reliable, and conforms to the specifications in
TDS-4.md and TDS-1.md.

## 9. References

1. Technical Design Specification: Transport Abstraction Layer (TDS-1.md)
   (search: internal-document)
2. Technical Design Specification: HTTP Transport Implementation (TDS-4.md)
   (search: internal-document)
3. Implementation Plan: HTTP Transport (IP-4.md) (search: internal-document)
4. pytest-asyncio Documentation (search: exa-pytest-asyncio.readthedocs.io)
5. Hypothesis for Property-Based Testing (search: exa-hypothesis.readthedocs.io)
6. aiohttp for Mock HTTP Server (search:
   exa-docs.aiohttp.org/en/stable/web.html)
