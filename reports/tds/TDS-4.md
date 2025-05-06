# Technical Design Specification: HTTP Transport Implementation

**Issue:** #4\
**Author:** pynector-architect\
**Date:** 2025-05-05\
**Status:** Draft

## 1. Introduction

This Technical Design Specification (TDS) defines the architecture and
implementation details for the HTTP Transport in the pynector project. The
design is based on the research findings documented in [RR-4.md](../rr/RR-4.md)
and conforms to the Transport protocol defined in [TDS-1.md](./TDS-1.md).

### 1.1 Purpose

The HTTP Transport provides an implementation of the Transport Protocol using
the `httpx` library, enabling efficient and reliable HTTP communication with the
following characteristics:

- Fully asynchronous HTTP client built on `httpx.AsyncClient`
- Proper connection pooling and resource management
- Comprehensive error handling with mapping to the Transport error hierarchy
- Support for various HTTP features (query parameters, headers, form data, JSON,
  files)
- Configurable retry mechanism for transient failures

### 1.2 Scope

This specification covers:

- The `HTTPTransport` class implementation
- Configuration options (base URL, headers, timeouts)
- Resource management (`AsyncClient` lifecycle)
- Retry logic using exponential backoff
- Error mapping to the Transport error hierarchy
- Support for various HTTP request/response types

## 2. Architecture

The `HTTPTransport` class implements the Transport Protocol defined in TDS-1.md,
providing HTTP-specific functionality while adhering to the protocol interface.

### 2.1 Component Diagram

```
┌─────────────────────────────────────┐
│           Client Application        │
└───────────────┬─────────────────────┘
                │
                ▼
┌─────────────────────────────────────┐
│     HTTPTransportFactory            │
└───────────────┬─────────────────────┘
                │ creates
                ▼
┌─────────────────────────────────────┐
│     HTTPTransport                   │
├─────────────────────────────────────┤
│  - connect()                        │
│  - disconnect()                     │
│  - send(message)                    │
│  - receive() -> AsyncIterator       │
└───────────────┬─────────────────────┘
                │ uses
                ▼
┌─────────────────────────────────────┐
│     httpx.AsyncClient               │
└─────────────────────────────────────┘
```

### 2.2 Integration with Transport Layer

The `HTTPTransport` class implements the Transport Protocol interface, allowing
it to be used interchangeably with other Transport implementations. It
integrates with the Transport Abstraction Layer as follows:

1. The `HTTPTransportFactory` creates configured instances of `HTTPTransport`
2. The `HTTPTransport` uses `httpx.AsyncClient` for HTTP communication
3. The `HTTPTransport` maps HTTP-specific errors to the Transport error
   hierarchy
4. Messages are serialized/deserialized according to the Message Protocol

## 3. HTTPTransport Implementation

The `HTTPTransport` class implements the Transport Protocol, providing
HTTP-specific functionality through `httpx.AsyncClient`.

### 3.1 Class Definition

```python
from typing import Dict, Any, Optional, Union, AsyncIterator, TypeVar, Type, Generic, cast
import httpx
import asyncio
from contextlib import asynccontextmanager

from pynector.transport.base import Transport, Message, TransportError
from pynector.transport.errors import (
    ConnectionError,
    ConnectionTimeoutError,
    ConnectionRefusedError,
    MessageError
)

T = TypeVar('T', bound=Message)

class HTTPTransport(Generic[T]):
    """HTTP transport implementation using httpx.AsyncClient."""

    def __init__(
        self,
        base_url: str = "",
        headers: Optional[Dict[str, str]] = None,
        timeout: Union[float, httpx.Timeout] = 10.0,
        max_retries: int = 3,
        retry_backoff_factor: float = 0.5,
        retry_status_codes: Optional[set[int]] = None,
        follow_redirects: bool = True,
        verify_ssl: bool = True,
        http2: bool = False,
    ):
        """Initialize the transport with configuration options.

        Args:
            base_url: The base URL for all requests
            headers: Default headers to include in all requests
            timeout: Request timeout in seconds or httpx.Timeout instance
            max_retries: Maximum number of retry attempts for transient errors
            retry_backoff_factor: Factor for exponential backoff between retries
            retry_status_codes: HTTP status codes that should trigger a retry (default: 429, 500, 502, 503, 504)
            follow_redirects: Whether to automatically follow redirects
            verify_ssl: Whether to verify SSL certificates
            http2: Whether to enable HTTP/2 support
        """
        self.base_url = base_url
        self.headers = headers or {}
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_factor = retry_backoff_factor
        self.retry_status_codes = retry_status_codes or {429, 500, 502, 503, 504}
        self.follow_redirects = follow_redirects
        self.verify_ssl = verify_ssl
        self.http2 = http2

        self._client: Optional[httpx.AsyncClient] = None
        self._message_type: Optional[Type[T]] = None

    async def connect(self) -> None:
        """Establish the connection by initializing the AsyncClient.

        Raises:
            ConnectionError: If the connection cannot be established
            ConnectionTimeoutError: If the connection attempt times out
        """
        if self._client is None:
            try:
                self._client = httpx.AsyncClient(
                    base_url=self.base_url,
                    headers=self.headers,
                    timeout=self.timeout,
                    follow_redirects=self.follow_redirects,
                    verify=self.verify_ssl,
                    http2=self.http2,
                )
            except httpx.ConnectError as e:
                raise ConnectionError(f"Failed to establish connection: {e}")
            except httpx.ConnectTimeout as e:
                raise ConnectionTimeoutError(f"Connection attempt timed out: {e}")
            except Exception as e:
                raise TransportError(f"Unexpected error during connection: {e}")

    async def disconnect(self) -> None:
        """Close the connection by closing the AsyncClient."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def send(self, message: T) -> None:
        """Send a message over the HTTP transport.

        Args:
            message: The message to send

        Raises:
            ConnectionError: If the connection is closed or broken
            HTTPTransportError: For HTTP-specific errors
            MessageError: For message serialization errors
        """
        if self._client is None:
            raise ConnectionError("Transport not connected")

        # Store message type for deserialization
        if self._message_type is None:
            self._message_type = type(message)

        # Extract request parameters from message
        headers = self._extract_headers(message)
        method, url, request_kwargs = self._prepare_request(message)

        try:
            data = message.serialize()
        except Exception as e:
            raise MessageError(f"Failed to serialize message: {e}")

        # Set content based on content-type if not overridden in request_kwargs
        if "content" not in request_kwargs and "json" not in request_kwargs and "data" not in request_kwargs:
            request_kwargs["content"] = data

        # Implement retry logic with exponential backoff
        retry_count = 0
        while True:
            try:
                response = await self._client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    **request_kwargs
                )

                # Raise for status but handle retryable errors separately
                if response.status_code >= 400:
                    if response.status_code in self.retry_status_codes and retry_count < self.max_retries:
                        retry_count += 1
                        backoff_time = self.retry_backoff_factor * (2 ** (retry_count - 1))
                        await asyncio.sleep(backoff_time)
                        continue

                    # Map HTTP status codes to appropriate exceptions
                    self._handle_error_response(response)

                # Success
                break

            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as e:
                # Network-related errors (potentially transient)
                retry_count += 1
                if retry_count > self.max_retries:
                    if isinstance(e, httpx.ConnectError):
                        raise ConnectionError(f"Connection failed: {e}")
                    elif isinstance(e, httpx.TimeoutException):
                        raise ConnectionTimeoutError(f"Request timed out: {e}")
                    else:
                        raise HTTPTransportError(f"HTTP request failed: {e}")

                backoff_time = self.retry_backoff_factor * (2 ** (retry_count - 1))
                await asyncio.sleep(backoff_time)

    async def receive(self) -> AsyncIterator[T]:
        """Receive messages from the HTTP transport.

        Returns:
            An async iterator yielding messages as they are received

        Raises:
            ConnectionError: If the connection is closed or broken
            HTTPTransportError: For HTTP-specific errors
            MessageError: For message deserialization errors
        """
        if self._client is None:
            raise ConnectionError("Transport not connected")

        if self._message_type is None:
            raise HTTPTransportError("No message type has been set")

        # For HTTP, receive is typically called after a send and yields a single response
        # Actual implementation depends on the specific HTTP usage pattern
        # This is a placeholder for a more specific implementation
        response = await self._get_next_response()
        if response:
            try:
                message = self._message_type.deserialize(response)
                yield message
            except Exception as e:
                raise MessageError(f"Failed to deserialize message: {e}")

    async def _get_next_response(self) -> Optional[bytes]:
        """Get the next response from the HTTP transport.

        This is a placeholder method that should be overridden by subclasses
        or set by users of this transport based on their specific HTTP
        communication pattern.

        Returns:
            The response data as bytes, or None if no response is available
        """
        # This is a placeholder - in a real implementation this would either:
        # 1. Return a response from a previous request stored in the instance
        # 2. Make a new request to poll for data (e.g., for long polling)
        # 3. Get data from a streaming endpoint
        return None

    def _extract_headers(self, message: T) -> Dict[str, str]:
        """Extract headers from the message.

        Args:
            message: The message to extract headers from

        Returns:
            A dictionary of header name to header value
        """
        # Merge default headers with message headers
        # Convert any non-string values to strings
        message_headers = message.get_headers()
        headers = {**self.headers}

        for name, value in message_headers.items():
            if isinstance(value, str):
                headers[name] = value
            else:
                headers[name] = str(value)

        # Set content-type if not already set
        if hasattr(message, "content_type") and "content-type" not in {k.lower() for k in headers}:
            headers["Content-Type"] = getattr(message, "content_type")

        return headers

    def _prepare_request(self, message: T) -> tuple[str, str, Dict[str, Any]]:
        """Prepare request parameters from the message.

        Args:
            message: The message to prepare request parameters from

        Returns:
            A tuple of (method, url, request_kwargs)
        """
        # Default values
        method = "POST"
        url = ""
        request_kwargs = {}

        # Extract method, url, and other parameters from message
        # This implementation assumes a specific structure for HTTP messages
        # Subclasses or extensions might override this for different formats
        payload = message.get_payload()

        if isinstance(payload, dict):
            method = payload.get("method", method).upper()
            url = payload.get("url", url)

            # Extract common HTTP parameters
            if "params" in payload:
                request_kwargs["params"] = payload["params"]
            if "json" in payload:
                request_kwargs["json"] = payload["json"]
            if "data" in payload:
                request_kwargs["data"] = payload["data"]
            if "files" in payload:
                request_kwargs["files"] = payload["files"]

            # Remove these keys so they don't appear twice
            for key in ["method", "url", "params", "json", "data", "files"]:
                if key in payload:
                    del payload[key]

            # Add remaining parameters
            request_kwargs.update(payload)

        return method, url, request_kwargs

    def _handle_error_response(self, response: httpx.Response) -> None:
        """Handle error responses by raising appropriate exceptions.

        Args:
            response: The error response

        Raises:
            HTTPTransportError: With appropriate status code and message
        """
        http_error = HTTPStatusError(
            response=response,
            message=f"HTTP error {response.status_code}: {response.reason_phrase}"
        )

        # Map HTTP status codes to specific error types
        if response.status_code == 401:
            raise HTTPUnauthorizedError(http_error)
        elif response.status_code == 403:
            raise HTTPForbiddenError(http_error)
        elif response.status_code == 404:
            raise HTTPNotFoundError(http_error)
        elif response.status_code == 408:
            raise HTTPTimeoutError(http_error)
        elif response.status_code == 429:
            raise HTTPTooManyRequestsError(http_error)
        elif 400 <= response.status_code < 500:
            raise HTTPClientError(http_error)
        elif 500 <= response.status_code < 600:
            raise HTTPServerError(http_error)
        else:
            raise http_error

    async def __aenter__(self) -> 'HTTPTransport[T]':
        """Enter the async context, establishing the connection.

        Returns:
            The transport instance

        Raises:
            ConnectionError: If the connection cannot be established
            ConnectionTimeoutError: If the connection attempt times out
        """
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the async context, closing the connection."""
        await self.disconnect()
```

### 3.2 Error Types

```python
from pynector.transport.errors import TransportSpecificError

class HTTPTransportError(TransportSpecificError):
    """Base class for HTTP transport-specific errors."""
    pass

class HTTPStatusError(HTTPTransportError):
    """Error representing an HTTP response status error."""

    def __init__(self, response: httpx.Response, message: str):
        self.response = response
        self.status_code = response.status_code
        super().__init__(message)

class HTTPClientError(HTTPStatusError):
    """HTTP client error (4xx)."""
    pass

class HTTPServerError(HTTPStatusError):
    """HTTP server error (5xx)."""
    pass

class HTTPUnauthorizedError(HTTPClientError):
    """HTTP unauthorized error (401)."""
    pass

class HTTPForbiddenError(HTTPClientError):
    """HTTP forbidden error (403)."""
    pass

class HTTPNotFoundError(HTTPClientError):
    """HTTP not found error (404)."""
    pass

class HTTPTimeoutError(HTTPClientError):
    """HTTP timeout error (408)."""
    pass

class HTTPTooManyRequestsError(HTTPClientError):
    """HTTP too many requests error (429)."""
    pass
```

### 3.3 HTTP Message Format

```python
from typing import Dict, Any, ClassVar, Type, Optional, Union
import json

class HttpMessage:
    """HTTP message implementation."""

    content_type: ClassVar[str] = "application/json"

    def __init__(
        self,
        method: str = "GET",
        url: str = "",
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Any] = None,
        form_data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        content: Optional[Union[str, bytes]] = None
    ):
        self.headers = headers or {}
        self.payload = {
            "method": method,
            "url": url
        }

        if params:
            self.payload["params"] = params
        if json_data is not None:
            self.payload["json"] = json_data
        if form_data:
            self.payload["data"] = form_data
        if files:
            self.payload["files"] = files
        if content:
            self.payload["content"] = content if isinstance(content, bytes) else content.encode('utf-8')

    def serialize(self) -> bytes:
        """Serialize the message to bytes."""
        data = {
            "headers": self.headers,
            "payload": self.payload
        }
        return json.dumps(data).encode('utf-8')

    @classmethod
    def deserialize(cls, data: bytes) -> 'HttpMessage':
        """Deserialize bytes to a message."""
        try:
            parsed = json.loads(data.decode('utf-8'))
            headers = parsed.get("headers", {})
            payload = parsed.get("payload", {})

            method = payload.get("method", "GET")
            url = payload.get("url", "")
            params = payload.get("params")
            json_data = payload.get("json")
            form_data = payload.get("data")
            files = payload.get("files")
            content = payload.get("content")

            return cls(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json_data=json_data,
                form_data=form_data,
                files=files,
                content=content
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON data: {e}")

    def get_headers(self) -> Dict[str, Any]:
        """Get the message headers."""
        return self.headers

    def get_payload(self) -> Any:
        """Get the message payload."""
        return self.payload
```

## 4. HTTPTransportFactory

The `HTTPTransportFactory` creates configured instances of `HTTPTransport`
according to the TransportFactory protocol.

```python
from typing import Dict, Any, Optional, Type, TypeVar

from pynector.transport.base import Message
from pynector.transport.http import HTTPTransport

T = TypeVar('T', bound=Message)

class HTTPTransportFactory:
    """Factory for creating HTTP transport instances."""

    def __init__(
        self,
        base_url: str,
        message_type: Type[T],
        default_headers: Optional[Dict[str, str]] = None,
        default_timeout: float = 30.0,
        default_max_retries: int = 3,
        default_retry_backoff_factor: float = 0.5,
        default_retry_status_codes: Optional[set[int]] = None,
        default_follow_redirects: bool = True,
        default_verify_ssl: bool = True,
        default_http2: bool = False,
    ):
        """Initialize the factory with default configuration.

        Args:
            base_url: The base URL for all requests
            message_type: The message type to use for deserialization
            default_headers: Default headers to include in all requests
            default_timeout: Default request timeout in seconds
            default_max_retries: Default maximum number of retry attempts
            default_retry_backoff_factor: Default factor for exponential backoff
            default_retry_status_codes: Default HTTP status codes that should trigger a retry
            default_follow_redirects: Default whether to automatically follow redirects
            default_verify_ssl: Default whether to verify SSL certificates
            default_http2: Default whether to enable HTTP/2 support
        """
        self.base_url = base_url
        self.message_type = message_type
        self.default_headers = default_headers or {}
        self.default_timeout = default_timeout
        self.default_max_retries = default_max_retries
        self.default_retry_backoff_factor = default_retry_backoff_factor
        self.default_retry_status_codes = default_retry_status_codes or {429, 500, 502, 503, 504}
        self.default_follow_redirects = default_follow_redirects
        self.default_verify_ssl = default_verify_ssl
        self.default_http2 = default_http2

    def create_transport(self, **kwargs: Any) -> HTTPTransport[T]:
        """Create a new HTTP transport instance.

        Args:
            **kwargs: HTTP transport configuration options.
                - headers: Optional[Dict[str, str]] - Additional headers to include
                - timeout: Optional[Union[float, httpx.Timeout]] - Request timeout
                - max_retries: Optional[int] - Maximum number of retry attempts
                - retry_backoff_factor: Optional[float] - Factor for exponential backoff
                - retry_status_codes: Optional[set[int]] - Status codes that trigger a retry
                - follow_redirects: Optional[bool] - Whether to follow redirects
                - verify_ssl: Optional[bool] - Whether to verify SSL certificates
                - http2: Optional[bool] - Whether to enable HTTP/2 support

        Returns:
            A new HTTP transport instance.
        """
        # Merge defaults with provided options
        headers = {**self.default_headers, **(kwargs.get('headers', {}))}
        timeout = kwargs.get('timeout', self.default_timeout)
        max_retries = kwargs.get('max_retries', self.default_max_retries)
        retry_backoff_factor = kwargs.get('retry_backoff_factor', self.default_retry_backoff_factor)
        retry_status_codes = kwargs.get('retry_status_codes', self.default_retry_status_codes)
        follow_redirects = kwargs.get('follow_redirects', self.default_follow_redirects)
        verify_ssl = kwargs.get('verify_ssl', self.default_verify_ssl)
        http2 = kwargs.get('http2', self.default_http2)

        transport = HTTPTransport[T](
            base_url=self.base_url,
            headers=headers,
            timeout=timeout,
            max_retries=max_retries,
            retry_backoff_factor=retry_backoff_factor,
            retry_status_codes=retry_status_codes,
            follow_redirects=follow_redirects,
            verify_ssl=verify_ssl,
            http2=http2,
        )

        # Set message type for deserialization
        transport._message_type = self.message_type

        return transport
```

## 5. Advanced Features

### 5.1 Streaming Support

The `HTTPTransport` can be extended to support streaming responses:

```python
async def stream_response(self, message: T) -> AsyncIterator[bytes]:
    """Stream a response from the HTTP transport.

    Args:
        message: The message to send

    Returns:
        An async iterator yielding chunks of the response as they are received

    Raises:
        ConnectionError: If the connection is closed or broken
        HTTPTransportError: For HTTP-specific errors
    """
    if self._client is None:
        raise ConnectionError("Transport not connected")

    # Extract request parameters from message
    headers = self._extract_headers(message)
    method, url, request_kwargs = self._prepare_request(message)

    try:
        data = message.serialize()
    except Exception as e:
        raise MessageError(f"Failed to serialize message: {e}")

    # Set streaming mode
    request_kwargs["stream"] = True

    try:
        async with self._client.stream(
            method=method,
            url=url,
            headers=headers,
            content=data,
            **request_kwargs
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                yield chunk
    except httpx.HTTPStatusError as e:
        self._handle_error_response(e.response)
    except httpx.ConnectError as e:
        raise ConnectionError(f"Connection failed: {e}")
    except httpx.TimeoutException as e:
        raise ConnectionTimeoutError(f"Request timed out: {e}")
    except Exception as e:
        raise HTTPTransportError(f"HTTP request failed: {e}")
```

### 5.2 Custom Response Handlers

The `HTTPTransport` can be extended with custom response handlers:

```python
class HTTPTransportWithResponseHandler(HTTPTransport[T]):
    """HTTP transport with custom response handler."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._response_handler: Optional[Callable[[httpx.Response], Optional[bytes]]] = None
        self._last_response: Optional[httpx.Response] = None

    def set_response_handler(self, handler: Callable[[httpx.Response], Optional[bytes]]) -> None:
        """Set a custom response handler.

        Args:
            handler: A function that takes a response and returns bytes or None
        """
        self._response_handler = handler

    async def send(self, message: T) -> None:
        """Send a message and store the response for later handling."""
        # ... similar to base implementation but store the response
        self._last_response = response

    async def _get_next_response(self) -> Optional[bytes]:
        """Get the next response using the custom handler if set."""
        if self._last_response is None:
            return None

        if self._response_handler is not None:
            return self._response_handler(self._last_response)

        return self._last_response.content
```

### 5.3 Circuit Breaker Pattern

The `HTTPTransport` can implement the circuit breaker pattern for improved
resilience:

```python
class HTTPTransportWithCircuitBreaker(HTTPTransport[T]):
    """HTTP transport with circuit breaker pattern."""

    def __init__(self, *args, failure_threshold: int = 5, reset_timeout: float = 60.0, **kwargs):
        super().__init__(*args, **kwargs)
        self._failure_count = 0
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._circuit_open = False
        self._last_failure_time = 0.0

    async def send(self, message: T) -> None:
        """Send a message with circuit breaker logic."""
        # Check if circuit is open
        if self._circuit_open:
            current_time = time.time()
            if current_time - self._last_failure_time >= self._reset_timeout:
                # Try to reset the circuit
                self._circuit_open = False
                self._failure_count = 0
            else:
                raise CircuitOpenError(f"Circuit is open until {self._last_failure_time + self._reset_timeout}")

        try:
            await super().send(message)
            # Reset failure count on success
            self._failure_count = 0
        except (ConnectionError, HTTPServerError) as e:
            # Increment failure count
            self._failure_count += 1
            if self._failure_count >= self._failure_threshold:
                # Open the circuit
                self._circuit_open = True
                self._last_failure_time = time.time()
            # Re-raise the exception
            raise
```

## 6. Implementation Considerations

### 6.1 HTTP Client Management

The `HTTPTransport` manages a single `httpx.AsyncClient` instance to maximize
connection pooling benefits. The client is created during `connect()` and closed
during `disconnect()`.

Key considerations:

1. **Connection pooling:** Using a single client instance enables connection
   pooling for multiple requests to the same host
2. **Resource cleanup:** The client's resources are properly cleaned up using
   the `aclose()` method
3. **Context management:** The transport supports the async context management
   protocol for proper resource management

### 6.2 Retry Logic

The `HTTPTransport` implements a configurable retry mechanism using exponential
backoff:

1. **Retry conditions:** Retries are performed for transient errors (connection
   errors, timeouts) and configurable HTTP status codes
2. **Exponential backoff:** The retry delay increases exponentially with each
   attempt to avoid overwhelming the server
3. **Maximum attempts:** A configurable maximum number of retry attempts
   prevents infinite retry loops

### 6.3 Error Handling

HTTP-specific errors are mapped to the Transport error hierarchy defined in
TDS-1.md:

1. **ConnectionError:** For connection-related errors (connect errors, timeouts)
2. **MessageError:** For message serialization/deserialization errors
3. **HTTPTransportError:** Base class for HTTP-specific errors (derived from
   TransportSpecificError)
4. **Status-specific errors:** Specialized error types for different HTTP status
   codes

### 6.4 Security Considerations

1. **SSL verification:** SSL certificate verification is enabled by default and
   configurable
2. **Timeout handling:** All operations have configurable timeouts to prevent
   hanging
3. **Header sanitization:** Headers are sanitized to prevent injection attacks

## 7. Usage Examples

### 7.1 Basic Usage

```python
from pynector.transport.http import HTTPTransport, HttpMessage
from pynector.transport.http.factory import HTTPTransportFactory

# Create a message
message = HttpMessage(
    method="GET",
    url="/api/data",
    headers={"Accept": "application/json"}
)

# Using the transport directly
async with HTTPTransport(base_url="https://api.example.com") as transport:
    await transport.send(message)
    async for response in transport.receive():
        print(response.get_payload())

# Using the factory
factory = HTTPTransportFactory(
    base_url="https://api.example.com",
    message_type=HttpMessage,
    default_headers={"User-Agent": "pynector/1.0"}
)

transport = factory.create_transport(timeout=5.0)
async with transport:
    await transport.send(message)
    async for response in transport.receive():
        print(response.get_payload())
```

### 7.2 Error Handling

```python
from pynector.transport.http import HTTPTransport, HttpMessage
from pynector.transport.http.errors import HTTPNotFoundError, HTTPServerError

async def send_with_error_handling(transport: HTTPTransport[HttpMessage], message: HttpMessage):
    try:
        async with transport:
            await transport.send(message)
            async for response in transport.receive():
                process_response(response)
    except HTTPNotFoundError as e:
        print(f"Resource not found: {e}")
    except HTTPServerError as e:
        print(f"Server error: {e}")
    except ConnectionError as e:
        print(f"Connection error: {e}")
```

### 7.3 Streaming Example

```python
from pynector.transport.http import HTTPTransport, HttpMessage

async def stream_file(transport: HTTPTransport[HttpMessage], url: str, file_path: str):
    message = HttpMessage(
        method="GET",
        url=url
    )

    async with transport:
        with open(file_path, "wb") as f:
            async for chunk in transport.stream_response(message):
                f.write(chunk)
```

## 8. Conclusion

The HTTP Transport implementation provides a robust and flexible mechanism for
HTTP communication within the pynector project. By leveraging the `httpx`
library and implementing the Transport protocol defined in TDS-1.md, it offers:

1. **Reliability:** Through proper connection management, retry logic, and error
   handling
2. **Flexibility:** Through support for various HTTP features and configurations
3. **Maintainability:** Through clear separation of concerns and comprehensive
   error handling
4. **Extensibility:** Through the factory pattern and ability to extend with
   additional functionality

This implementation balances feature richness with simplicity, providing a solid
foundation for HTTP communication in the pynector project.

## 9. References

1. Research Report: Implementing an Async HTTP Transport with httpx (RR-4.md)
   (search: internal-document)
2. Technical Design Specification: Transport Abstraction Layer (TDS-1.md)
   (search: internal-document)
3. httpx Documentation - Async Support (search: exa-www.python-httpx.org/async/)
4. httpx Documentation - Clients (search:
   exa-www.python-httpx.org/advanced/clients/)
5. httpx Documentation - Transports (search:
   exa-www.python-httpx.org/advanced/transports/)
6. Circuit Breaker Pattern (search:
   exa-martinfowler.com/bliki/CircuitBreaker.html)
7. PEP 567 – Context Variables (search: exa-peps.python.org/pep-0567/)
8. PyPI - tenacity: Retry library for Python (search:
   exa-pypi.org/project/tenacity/)
