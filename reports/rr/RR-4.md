# Research Report: Implementing an Async HTTP Transport with httpx

**Issue:** #4\
**Author:** pynector-researcher\
**Date:** 2025-05-05\
**Status:** Complete

## 1. Executive Summary

This research report explores best practices for implementing an async HTTP
transport using `httpx`, conforming to the Transport protocol defined in Issue
#1. The report investigates connection pooling, resource management with async
context managers, retry/backoff logic for transient errors, error handling, and
support for various HTTP features.

Key findings:

- The `httpx.AsyncClient` provides a robust foundation for implementing the
  Transport protocol
- Connection pooling requires careful management of client instances
- Async context managers are essential for proper resource management
- Custom retry logic can be implemented, though httpx doesn't provide built-in
  retry mechanisms
- The transport should support various HTTP features like query parameters, form
  data, and file uploads

## 2. Introduction to httpx

httpx is a modern, fully featured HTTP client for Python that provides both
synchronous and asynchronous APIs. It offers several advantages over other HTTP
clients:

- Support for HTTP/1.1 and HTTP/2
- Async support with the `AsyncClient` class
- Connection pooling for efficient resource usage
- Streaming responses
- Timeout configuration
- Support for various authentication methods
- Compatible with WSGI and ASGI applications

**Source:** [httpx GitHub Repository](https://github.com/encode/httpx) (search:
exa-github.com/encode/httpx)

> "A broadly requests-compatible API. HTTP/1.1 and HTTP/2 support. Standard
> synchronous interface, but with async support if you need it."

## 3. Implementing the Transport Protocol with httpx

### 3.1 Connection Pooling

Connection pooling is a critical feature for efficient HTTP communication. The
`httpx.AsyncClient` implements connection pooling by default, which allows it to
reuse TCP connections for multiple requests to the same host.

Key findings on connection pooling:

1. **Client Instantiation:** To benefit from connection pooling, avoid creating
   multiple client instances, especially in "hot loops."

   **Source:** [httpx Async Support](https://www.python-httpx.org/async/)
   (search: exa-www.python-httpx.org/async/)

   > "In order to get the most benefit from connection pooling, make sure you're
   > not instantiating multiple client instances - for example by using
   > `async with` inside a 'hot loop'. This can be achieved either by having a
   > single scoped client that's passed throughout wherever it's needed, or by
   > having a single global client instance."

2. **Client vs. Top-level API:** Using the `AsyncClient` class provides
   connection pooling, while the top-level API functions create new connections
   for each request.

   **Source:** [httpx Clients](https://www.python-httpx.org/advanced/clients/)
   (search: exa-www.python-httpx.org/advanced/clients/)

   > "When you make requests using the top-level API as documented in the
   > Quickstart guide, HTTPX has to establish a new connection for every single
   > request (connections are not reused). As the number of requests to a host
   > increases, this quickly becomes inefficient. On the other hand, a Client
   > instance uses HTTP connection pooling."

3. **Connection Reuse:** The client will automatically reuse underlying TCP
   connections for requests to the same host.

   > "This means that when you make several requests to the same host, the
   > Client will reuse the underlying TCP connection, instead of recreating one
   > for every single request."

### 3.2 Resource Management with Async Context Managers

Proper resource management is essential for async applications. The
`httpx.AsyncClient` implements the async context manager protocol, allowing for
clean resource acquisition and release.

Key findings on resource management:

1. **Context Manager Usage:** The recommended way to use `AsyncClient` is with
   the async context manager pattern.

   **Source:**
   [Is it necessary to write async with AsyncClient?](https://stackoverflow.com/questions/72921224/is-it-necessary-to-write-async-with-asyncclient)
   (search:
   exa-stackoverflow.com/questions/72921224/is-it-necessary-to-write-async-with-asyncclient)

   > "Use async with httpx.AsyncClient() if you want a context-managed client."

2. **Explicit Cleanup:** If not using a context manager, resources must be
   explicitly cleaned up.

   > "Alternatively, use await client.aclose() if you want to close a client
   > explicitly."

3. **Resource Management Importance:** Proper resource management is crucial for
   applications that share networking resources.

   > "If you are going to be integrating an httpx.AsyncClient into a larger
   > application (ex. FastAPI), or have multiple instances of an
   > httpx.AsyncClient sharing the same networking resources, or your
   > application that use an httpx.AsyncClient is sharing the system with other
   > applications that also use networking resources, it is good practice to
   > make sure you call .aclose()."

4. **Structured Concurrency:** Context-managed clients support structured
   concurrency, which is important for background tasks.

   **Source:**
   [Enforcing AsyncClient as context-managed only?](https://github.com/encode/httpx/issues/769)
   (search: exa-github.com/encode/httpx/issues/769)

   > "If we ever wanted to support background tasks, then structured concurrency
   > means we'd want the client instances to be context-managed, so that we've
   > got well defined lifetimes for any background running tasks."

### 3.3 Error Handling and Retry Logic

httpx doesn't provide built-in retry mechanisms, but custom retry logic can be
implemented. Several approaches are possible:

1. **Manual Retry Implementation:** Implement retry logic manually using
   try/except blocks and backoff algorithms.

   **Source:**
   [How can I implement retry policy with httpx in Python?](https://stackoverflow.com/questions/77694820/how-can-i-implement-retry-policy-with-httpx-in-python)
   (search:
   exa-stackoverflow.com/questions/77694820/how-can-i-implement-retry-policy-with-httpx-in-python)

   > "I would like to implement a retry policy so that if a request fails, it is
   > retried, for example, up to 3 times. Is this possible and makes sense with
   > httpx and async?"

2. **Custom Transport with Retry:** Implement a custom transport that handles
   retries.

   **Source:** [Retry requests](https://github.com/encode/httpx/issues/108)
   (search: exa-github.com/encode/httpx/issues/108)

   > "urllib3 has a very convenient Retry utility that I have found to be quite
   > useful when dealing with flaky APIs. http3's Clients don't support this
   > sort of thing yet, but I would love it if they did!"

3. **Retry Configuration Options:** When implementing retry logic, consider
   these parameters:

   **Source:**
   [Python HTTPX - Retry Failed Requests](https://scrapeops.io/python-web-scraping-playbook/python-httpx-retry-failed-requests/)
   (search:
   exa-scrapeops.io/python-web-scraping-playbook/python-httpx-retry-failed-requests/)

   > "- `status_allowlist`: Works in the opposite way to `status_forcelist`.
   > Instead of specifying which status codes should trigger a retry, it defines
   > a list of status codes that are explicitly allowed to retry."

   > "- `method_retry`: A callable that takes the HTTP method and response
   > status code and returns `True` if a retry should be attempted for that
   > combination, and `False` otherwise. You can use this to implement custom
   > retry logic based on specific conditions."

### 3.4 Supporting HTTP Features

httpx supports various HTTP features that should be incorporated into the
Transport implementation:

1. **Query Parameters:** httpx supports query parameters through the `params`
   argument.

2. **Form Data:** Form data can be sent using the `data` parameter.

   **Source:**
   [Post multipart/form-data using pythons httpx library](https://stackoverflow.com/questions/79391995/post-multipart-form-data-using-pythons-httpx-library-only-form-data)
   (search:
   exa-stackoverflow.com/questions/79391995/post-multipart-form-data-using-pythons-httpx-library-only-form-data)

   > "The official documentation states that form fields should be passed using
   > the data keyword, using the dict object."

3. **JSON Data:** JSON data can be sent using the `json` parameter.

4. **File Uploads:** File uploads are supported through the `files` parameter.

   **Source:** [httpx Clients](https://www.python-httpx.org/advanced/clients/)
   (search: exa-www.python-httpx.org/advanced/clients/)

   > "As mentioned in the quickstart multipart file encoding is available by
   > passing a dictionary with the name of the payloads as keys and either tuple
   > of elements or a file-like object or a string as values."

5. **Streaming Responses:** httpx supports streaming responses, which is useful
   for handling large responses efficiently.

   **Source:** [httpx Async Support](https://www.python-httpx.org/async/)
   (search: exa-www.python-httpx.org/async/)

   > "- `Response.aiter_bytes()` - For streaming the response content as bytes.
   >
   > - `Response.aiter_text()` - For streaming the response content as text.
   > - `Response.aiter_lines()` - For streaming the response content as lines of
   >   text.
   > - `Response.aiter_raw()` - For streaming the raw response bytes, without
   >   applying content decoding."

## 4. Custom Transport Implementation

httpx allows implementing custom transports by subclassing `AsyncBaseTransport`.
This is useful for implementing the Transport protocol defined in Issue #1.

**Source:**
[httpx Transports](https://www.python-httpx.org/advanced/transports/) (search:
exa-www.python-httpx.org/advanced/transports/)

> "You should either subclass `httpx.BaseTransport` to implement a transport to
> use with `Client`, or subclass `httpx.AsyncBaseTransport` to implement a
> transport to use with `AsyncClient`."

The custom transport implementation should:

1. Implement the `handle_async_request` method
2. Handle connection pooling
3. Manage resources properly
4. Implement error handling and retry logic
5. Support various HTTP features

**Source:**
[Finalising the Transport API for 1.0](https://github.com/encode/httpx/issues/1274)
(search: exa-github.com/encode/httpx/issues/1274)

> "There's a few bits of thinking around the Transport API that we'd like to be
> completely set on before we roll with a 1.0 release. - We should consider
> splitting the sync/async interface as `.request`/ `.arequest`. This would
> allow transport implementations that support both sync+async usage, which
> would be a really nice usability for some use-cases."

## 5. Best Practices

Based on the research, here are the best practices for implementing an async
HTTP transport with httpx:

1. **Use AsyncClient with Context Manager:**
   - Always use `AsyncClient` with the async context manager pattern
   - Ensure proper resource cleanup with `__aenter__` and `__aexit__` methods

2. **Efficient Connection Pooling:**
   - Avoid creating multiple client instances
   - Pass a single client instance throughout the application
   - Consider using a global client instance for simple applications

3. **Proper Error Handling:**
   - Implement comprehensive error handling
   - Consider implementing retry logic for transient errors
   - Use exponential backoff for retries

4. **Resource Management:**
   - Ensure all resources are properly cleaned up
   - Use `aclose()` method when not using context managers
   - Consider the lifetime of background tasks

5. **Support for HTTP Features:**
   - Implement support for query parameters, form data, JSON, and file uploads
   - Support streaming responses for efficient handling of large responses

## 6. Recommendations for pynector

Based on the research, here are recommendations for implementing an async HTTP
transport using httpx in the pynector project:

### 6.1 Implementation Approach

1. **Implement the TransportProtocol using httpx.AsyncClient:**
   - Create a class that implements the TransportProtocol defined in Issue #1
   - Use httpx.AsyncClient as the underlying HTTP client
   - Implement async context manager protocol

2. **Connection Pooling:**
   - Use a single AsyncClient instance for connection pooling
   - Configure appropriate timeouts and limits

3. **Error Handling and Retry Logic:**
   - Implement custom retry logic with exponential backoff
   - Handle common HTTP errors appropriately
   - Consider implementing circuit breaker pattern for persistent failures

4. **Resource Management:**
   - Ensure proper cleanup of resources in `__aexit__` method
   - Handle exceptions appropriately

### 6.2 Proposed Implementation

```python
from typing import AsyncIterator, Dict, Any, Optional, Union
import httpx
import asyncio
from contextlib import asynccontextmanager

class HttpxTransport:
    """HTTP transport implementation using httpx."""

    def __init__(
        self,
        base_url: str = "",
        headers: Optional[Dict[str, str]] = None,
        timeout: Union[float, httpx.Timeout] = 10.0,
        max_retries: int = 3,
        retry_backoff_factor: float = 0.5,
    ):
        """Initialize the transport with configuration options."""
        self.base_url = base_url
        self.headers = headers or {}
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_factor = retry_backoff_factor
        self._client: Optional[httpx.AsyncClient] = None

    async def connect(self) -> None:
        """Establish the connection."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.headers,
                timeout=self.timeout,
            )

    async def disconnect(self) -> None:
        """Close the connection."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def send(self, data: bytes, **kwargs) -> None:
        """Send data over the transport."""
        if self._client is None:
            raise RuntimeError("Transport not connected")

        url = kwargs.pop("url", "")
        method = kwargs.pop("method", "POST")

        # Extract common parameters
        params = kwargs.pop("params", None)
        headers = kwargs.pop("headers", None)

        # Handle different content types
        json_data = kwargs.pop("json", None)
        form_data = kwargs.pop("form", None)
        files = kwargs.pop("files", None)

        # Implement retry logic with exponential backoff
        retry_count = 0
        while True:
            try:
                response = await self._client.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=headers,
                    content=None if json_data or form_data or files else data,
                    json=json_data,
                    data=form_data,
                    files=files,
                    **kwargs
                )
                response.raise_for_status()
                return
            except httpx.HTTPStatusError as e:
                # Don't retry client errors (4xx) except specific ones
                if e.response.status_code < 500 and e.response.status_code != 429:
                    raise

                retry_count += 1
                if retry_count > self.max_retries:
                    raise

                # Calculate backoff time with exponential backoff
                backoff_time = self.retry_backoff_factor * (2 ** (retry_count - 1))
                await asyncio.sleep(backoff_time)
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as e:
                retry_count += 1
                if retry_count > self.max_retries:
                    raise

                backoff_time = self.retry_backoff_factor * (2 ** (retry_count - 1))
                await asyncio.sleep(backoff_time)

    async def receive(self) -> AsyncIterator[bytes]:
        """Receive data from the transport."""
        if self._client is None:
            raise RuntimeError("Transport not connected")

        # This is a placeholder - actual implementation would depend on
        # how the transport is expected to receive data
        yield b""

    async def __aenter__(self) -> 'HttpxTransport':
        """Enter the async context."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the async context."""
        await self.disconnect()
```

### 6.3 Extended Implementation

For a more complete implementation, consider:

1. **Streaming Support:**
   - Implement streaming for large request/response bodies
   - Use httpx's streaming capabilities

2. **Advanced Error Handling:**
   - Implement circuit breaker pattern
   - Add detailed logging for errors
   - Consider custom exception types

3. **Configuration Options:**
   - Allow configuration of connection pooling
   - Support for proxies
   - Configure SSL verification

## 7. Conclusion

Implementing an async HTTP transport using httpx provides a solid foundation for
the pynector project. The httpx library offers robust features for async HTTP
communication, connection pooling, and resource management.

By following the best practices outlined in this report and implementing the
proposed design, the pynector project can create a reliable, efficient, and
feature-rich HTTP transport that conforms to the Transport protocol defined in
Issue #1.

## 8. References

1. httpx Documentation - Async Support (search: exa-www.python-httpx.org/async/)
2. httpx Documentation - Clients (search:
   exa-www.python-httpx.org/advanced/clients/)
3. httpx Documentation - Transports (search:
   exa-www.python-httpx.org/advanced/transports/)
4. httpx Documentation - Quickstart (search:
   exa-www.python-httpx.org/quickstart/)
5. GitHub - encode/httpx (search: exa-github.com/encode/httpx)
6. GitHub Issue - Retry requests (search:
   exa-github.com/encode/httpx/issues/108)
7. GitHub Issue - Finalising the Transport API for 1.0 (search:
   exa-github.com/encode/httpx/issues/1274)
8. GitHub Issue - Enforcing AsyncClient as context-managed only? (search:
   exa-github.com/encode/httpx/issues/769)
9. Stack Overflow - How can I implement retry policy with httpx in Python?
   (search:
   exa-stackoverflow.com/questions/77694820/how-can-i-implement-retry-policy-with-httpx-in-python)
10. Stack Overflow - Is it necessary to write async with AsyncClient? (search:
    exa-stackoverflow.com/questions/72921224/is-it-necessary-to-write-async-with-asyncclient)
11. Stack Overflow - How does httpx client's connection pooling work? (search:
    exa-stackoverflow.com/questions/69916682/python-httpx-how-does-httpx-clients-connection-pooling-work)
12. Stack Overflow - Post multipart/form-data using pythons httpx library
    (search:
    exa-stackoverflow.com/questions/79391995/post-multipart-form-data-using-pythons-httpx-library-only-form-data)
13. ScrapeOps - Python HTTPX - Retry Failed Requests (search:
    exa-scrapeops.io/python-web-scraping-playbook/python-httpx-retry-failed-requests/)
14. Better Stack - Getting Started with HTTPX: Python's Modern HTTP Client
    (search:
    exa-betterstack.com/community/guides/scaling-python/httpx-explained/)
