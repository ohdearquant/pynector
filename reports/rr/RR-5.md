# Research Report: Async SDK Transport Wrapper for OpenAI and Anthropic

**Issue:** #5\
**Author:** pynector-researcher\
**Date:** 2025-05-05\
**Status:** Complete

## 1. Executive Summary

This research report explores best practices for implementing an async SDK
transport wrapper for OpenAI and Anthropic Python SDKs, conforming to the
Transport protocol defined in RR-1. The focus areas are handling streaming
responses, translating SDK-specific errors, authentication mechanisms, and
exposing SDK features consistently.

Key findings:

- Both OpenAI and Anthropic SDKs are built on httpx and offer similar async
  capabilities
- Streaming responses require different handling approaches for each SDK but can
  be unified
- Error handling can be standardized through a common error translation layer
- Authentication follows similar patterns but with different implementation
  details
- A facade pattern with adapter classes provides the most flexible approach for
  consistent SDK feature exposure

## 2. SDK Architecture Comparison

### 2.1 OpenAI Python SDK

The OpenAI Python SDK provides access to the OpenAI REST API with the following
characteristics:

- Built on httpx for both synchronous and asynchronous clients
- Generated from OpenAPI specification using Stainless
- Includes type definitions for all request params and response fields
- Offers helper functions for polling asynchronous operations
- Provides streaming helpers for processing stream events
- Authentication via API key (typically from environment variables)

**Source:** [OpenAI Python SDK GitHub](https://github.com/openai/openai-python)
(search: exa-github.com/openai/openai-python)

> "The OpenAI Python library provides convenient access to the OpenAI REST API
> from any Python 3.7+ application. It includes type definitions for all request
> params and response fields, and offers both synchronous and asynchronous
> clients powered by httpx."

### 2.2 Anthropic Python SDK

The Anthropic Python SDK provides access to the Anthropic REST API with similar
characteristics:

- Also built on httpx for both synchronous and asynchronous clients
- Includes type definitions for all request params and response fields
- Supports streaming responses
- Authentication via API key header
- Supports both direct API access and partner platforms (Amazon Bedrock, Google
  Cloud Vertex AI)

**Source:**
[Anthropic Python SDK GitHub](https://github.com/anthropics/anthropic-sdk-python)
(search: exa-github.com/anthropics/anthropic-sdk-python)

> "The Anthropic Python library provides convenient access to the Anthropic REST
> API from any Python 3.7+ application. It includes type definitions for all
> request params and response fields, and offers both synchronous and
> asynchronous clients powered by httpx."

### 2.3 Key Similarities and Differences

| Feature               | OpenAI SDK             | Anthropic SDK            |
| --------------------- | ---------------------- | ------------------------ |
| HTTP Client           | httpx                  | httpx                    |
| Async Support         | Yes                    | Yes                      |
| Streaming             | Event-based API        | with_streaming_response  |
| Error Handling        | Custom exceptions      | Standard HTTP exceptions |
| Authentication        | API key in client init | API key in header        |
| Response Format       | Structured objects     | Structured objects       |
| Optional Dependencies | No                     | No                       |

Both SDKs follow similar patterns in their implementation, making it feasible to
create a unified transport wrapper that conforms to the Transport protocol.

## 3. Handling Streaming Responses

### 3.1 OpenAI Streaming Implementation

OpenAI provides a sophisticated streaming implementation with an event-based
API:

```python
with client.beta.chat.completions.stream(
    model='gpt-4o-2024-08-06',
    messages=[...],
) as stream:
    for event in stream:
        if event.type == 'content.delta':
            print(event.content, flush=True, end='')
```

The stream yields different event types that allow tracking the progress of the
generation, accessing partial results, and handling different aspects of the
stream separately.

**Source:**
[OpenAI Python SDK Helpers](https://github.com/openai/openai-python/blob/main/helpers.md)
(search: exa-github.com/openai/openai-python/blob/main/helpers.md)

### 3.2 Anthropic Streaming Implementation

Anthropic provides a more basic streaming implementation using the
`with_streaming_response` method:

```python
with client.messages.create.with_streaming_response(
    model="claude-3-opus-20240229",
    messages=[...],
) as response:
    for chunk in response.iter_lines():
        # Process each chunk
```

The streaming response provides methods like `.read()`, `.text()`, `.json()`,
`.iter_bytes()`, `.iter_text()`, `.iter_lines()` or `.parse()`.

**Source:**
[Anthropic Python SDK GitHub](https://github.com/anthropics/anthropic-sdk-python)
(search: exa-github.com/anthropics/anthropic-sdk-python)

### 3.3 Unified Streaming Approach

To create a unified streaming interface that conforms to the Transport protocol,
we can implement an adapter pattern that normalizes the different streaming
approaches:

```python
async def receive(self) -> AsyncIterator[bytes]:
    """Receive data from the transport."""
    if self._sdk_type == "openai":
        async for event in self._stream:
            if event.type == "content.delta":
                yield event.delta.encode("utf-8")
    elif self._sdk_type == "anthropic":
        for chunk in self._response.iter_lines():
            yield chunk.encode("utf-8")
```

This approach allows the transport wrapper to present a consistent streaming
interface regardless of the underlying SDK.

## 4. Translating SDK-Specific Errors

### 4.1 OpenAI Error Handling

OpenAI SDK provides custom exception classes for different error types. These
exceptions contain detailed information about the error, including the HTTP
status code, error message, and additional context.

The SDK raises exceptions for various error conditions, including authentication
errors, rate limiting, and invalid requests.

### 4.2 Anthropic Error Handling

Anthropic SDK uses standard HTTP exceptions with specific error types:

- 400 - `invalid_request_error`: Format or content issues
- 401 - `authentication_error`: API key issues
- 403 - `permission_error`: Permission issues
- 404 - `not_found_error`: Resource not found
- 413 - `request_too_large`: Request exceeds maximum size

**Source:** [Anthropic API Errors](https://docs.anthropic.com/en/api/errors)
(search: exa-docs.anthropic.com/en/api/errors)

### 4.3 Error Translation Layer

To provide consistent error handling across both SDKs, we can implement an error
translation layer that maps SDK-specific errors to a common set of exceptions:

```python
class TransportError(Exception):
    """Base class for all transport errors."""
    pass

class AuthenticationError(TransportError):
    """Authentication error."""
    pass

class RateLimitError(TransportError):
    """Rate limit error."""
    pass

class InvalidRequestError(TransportError):
    """Invalid request error."""
    pass

def translate_error(sdk_error):
    """Translate SDK-specific errors to transport errors."""
    if isinstance(sdk_error, openai.AuthenticationError):
        return AuthenticationError(str(sdk_error))
    elif isinstance(sdk_error, anthropic.APIStatusError) and sdk_error.status_code == 401:
        return AuthenticationError(str(sdk_error))
    # Additional error mappings...
```

This approach ensures that the transport wrapper presents a consistent error
interface regardless of the underlying SDK.

## 5. Authentication Mechanisms

### 5.1 OpenAI Authentication

OpenAI SDK uses an API key for authentication, which can be provided in several
ways:

1. As an argument to the client constructor:
   ```python
   client = OpenAI(api_key="sk-...")
   ```

2. From environment variables:
   ```python
   # Uses os.environ.get("OPENAI_API_KEY")
   client = OpenAI()
   ```

**Source:** [OpenAI Python SDK GitHub](https://github.com/openai/openai-python)
(search: exa-github.com/openai/openai-python)

### 5.2 Anthropic Authentication

Anthropic SDK also uses an API key for authentication, with similar approaches:

1. As an argument to the client constructor:
   ```python
   client = anthropic.Anthropic(api_key="sk-ant-...")
   ```

2. From environment variables:
   ```python
   # Uses os.environ.get("ANTHROPIC_API_KEY")
   client = anthropic.Anthropic()
   ```

**Source:**
[Anthropic API Getting Started](https://docs.anthropic.com/en/api/getting-started)
(search: exa-docs.anthropic.com/en/api/getting-started)

### 5.3 Unified Authentication Approach

To provide a consistent authentication interface, the transport wrapper can
accept an API key and handle the SDK-specific authentication details:

```python
class SDKTransport:
    def __init__(self, api_key=None, sdk_type="openai"):
        self.api_key = api_key
        self.sdk_type = sdk_type
        self._client = None

    async def connect(self):
        if self.sdk_type == "openai":
            self._client = OpenAI(api_key=self.api_key)
        elif self.sdk_type == "anthropic":
            self._client = anthropic.Anthropic(api_key=self.api_key)
```

This approach allows the transport wrapper to handle authentication consistently
while respecting the specific requirements of each SDK.

## 6. Exposing SDK Features Consistently

### 6.1 Feature Comparison

Both SDKs offer similar core features but with different APIs:

| Feature          | OpenAI SDK                       | Anthropic SDK                                    |
| ---------------- | -------------------------------- | ------------------------------------------------ |
| Chat Completions | client.chat.completions.create() | client.messages.create()                         |
| Streaming        | client.chat.completions.stream() | client.messages.create.with_streaming_response() |
| Models           | Specified in request             | Specified in request                             |
| Function Calling | tools parameter                  | tools parameter                                  |

### 6.2 Facade Pattern

To expose SDK features consistently, we can implement a facade pattern with
adapter classes for each SDK:

```python
class SDKAdapter:
    """Base adapter class for SDK-specific implementations."""

    async def complete(self, prompt, **kwargs):
        """Generate a completion for the given prompt."""
        raise NotImplementedError

    async def stream(self, prompt, **kwargs):
        """Stream a completion for the given prompt."""
        raise NotImplementedError

class OpenAIAdapter(SDKAdapter):
    def __init__(self, client):
        self.client = client

    async def complete(self, prompt, **kwargs):
        messages = [{"role": "user", "content": prompt}]
        response = await self.client.chat.completions.create(
            messages=messages,
            **kwargs
        )
        return response.choices[0].message.content

    async def stream(self, prompt, **kwargs):
        messages = [{"role": "user", "content": prompt}]
        async with self.client.chat.completions.stream(
            messages=messages,
            **kwargs
        ) as stream:
            for event in stream:
                if event.type == "content.delta":
                    yield event.delta.encode("utf-8")

class AnthropicAdapter(SDKAdapter):
    def __init__(self, client):
        self.client = client

    async def complete(self, prompt, **kwargs):
        response = await self.client.messages.create(
            messages=[{"role": "user", "content": prompt}],
            **kwargs
        )
        return response.content[0].text

    async def stream(self, prompt, **kwargs):
        with self.client.messages.create.with_streaming_response(
            messages=[{"role": "user", "content": prompt}],
            **kwargs
        ) as response:
            for chunk in response.iter_lines():
                yield chunk.encode("utf-8")
```

This approach allows the transport wrapper to present a consistent interface
while leveraging the specific features of each SDK.

## 7. Recommendations for pynector

Based on the research, here are recommendations for implementing an async SDK
transport wrapper for OpenAI and Anthropic Python SDKs:

### 7.1 Architecture

1. **Implement the Transport Protocol using Adapter Pattern:**
   - Create a class that implements the TransportProtocol defined in RR-1
   - Use adapter classes for SDK-specific implementations
   - Implement async context manager protocol

2. **Error Handling:**
   - Implement a common error translation layer
   - Map SDK-specific errors to transport-specific exceptions
   - Provide detailed error information

3. **Streaming Support:**
   - Implement a unified streaming interface
   - Handle SDK-specific streaming implementations
   - Provide consistent event types

4. **Authentication:**
   - Support API key authentication
   - Allow environment variable configuration
   - Handle SDK-specific authentication details

### 7.2 Proposed Implementation

```python
from typing import AsyncIterator, Dict, Any, Optional, Union
import os
import httpx
import openai
import anthropic
from contextlib import asynccontextmanager

class SDKTransportError(Exception):
    """Base class for all SDK transport errors."""
    pass

class SDKTransport:
    """SDK transport implementation using OpenAI and Anthropic SDKs."""

    def __init__(
        self,
        sdk_type: str = "openai",
        api_key: Optional[str] = None,
        base_url: str = "",
        timeout: float = 60.0,
    ):
        """Initialize the transport with configuration options."""
        self.sdk_type = sdk_type
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self._client = None
        self._adapter = None

    async def connect(self) -> None:
        """Establish the connection."""
        if self._client is not None:
            return

        try:
            if self.sdk_type == "openai":
                self._client = openai.AsyncOpenAI(
                    api_key=self.api_key or os.environ.get("OPENAI_API_KEY"),
                    base_url=self.base_url or None,
                    timeout=self.timeout,
                )
                self._adapter = OpenAIAdapter(self._client)
            elif self.sdk_type == "anthropic":
                self._client = anthropic.AsyncAnthropic(
                    api_key=self.api_key or os.environ.get("ANTHROPIC_API_KEY"),
                    base_url=self.base_url or None,
                    timeout=httpx.Timeout(self.timeout),
                )
                self._adapter = AnthropicAdapter(self._client)
            else:
                raise ValueError(f"Unsupported SDK type: {self.sdk_type}")
        except Exception as e:
            raise SDKTransportError(f"Failed to connect: {str(e)}") from e

    async def disconnect(self) -> None:
        """Close the connection."""
        self._client = None
        self._adapter = None

    async def send(self, data: bytes, **kwargs) -> None:
        """Send data over the transport."""
        if self._adapter is None:
            raise SDKTransportError("Transport not connected")

        try:
            prompt = data.decode("utf-8")
            await self._adapter.complete(prompt, **kwargs)
        except Exception as e:
            raise SDKTransportError(f"Failed to send data: {str(e)}") from e

    async def receive(self) -> AsyncIterator[bytes]:
        """Receive data from the transport."""
        if self._adapter is None:
            raise SDKTransportError("Transport not connected")

        try:
            prompt = "Generate a response"  # Default prompt
            async for chunk in self._adapter.stream(prompt):
                yield chunk
        except Exception as e:
            raise SDKTransportError(f"Failed to receive data: {str(e)}") from e

    async def __aenter__(self) -> 'SDKTransport':
        """Enter the async context."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the async context."""
        await self.disconnect()

class SDKAdapter:
    """Base adapter class for SDK-specific implementations."""

    async def complete(self, prompt, **kwargs):
        """Generate a completion for the given prompt."""
        raise NotImplementedError

    async def stream(self, prompt, **kwargs):
        """Stream a completion for the given prompt."""
        raise NotImplementedError

class OpenAIAdapter(SDKAdapter):
    def __init__(self, client):
        self.client = client

    async def complete(self, prompt, **kwargs):
        messages = [{"role": "user", "content": prompt}]
        response = await self.client.chat.completions.create(
            messages=messages,
            model=kwargs.get("model", "gpt-3.5-turbo"),
        )
        return response.choices[0].message.content

    async def stream(self, prompt, **kwargs):
        messages = [{"role": "user", "content": prompt}]
        async with self.client.chat.completions.stream(
            messages=messages,
            model=kwargs.get("model", "gpt-3.5-turbo"),
        ) as stream:
            async for event in stream:
                if event.type == "content.delta":
                    yield event.delta.encode("utf-8")

class AnthropicAdapter(SDKAdapter):
    def __init__(self, client):
        self.client = client

    async def complete(self, prompt, **kwargs):
        response = await self.client.messages.create(
            messages=[{"role": "user", "content": prompt}],
            model=kwargs.get("model", "claude-3-sonnet-20240229"),
        )
        return response.content[0].text

    async def stream(self, prompt, **kwargs):
        async with self.client.messages.create.with_streaming_response(
            messages=[{"role": "user", "content": prompt}],
            model=kwargs.get("model", "claude-3-sonnet-20240229"),
        ) as response:
            async for chunk in response.iter_text():
                yield chunk.encode("utf-8")
```

### 7.3 Implementation Considerations

1. **Error Handling:**
   - Implement more comprehensive error translation
   - Add retry logic for transient errors
   - Consider circuit breaker pattern for persistent failures

2. **Configuration Options:**
   - Support additional SDK-specific configuration options
   - Allow customization of default parameters
   - Provide convenience methods for common operations

3. **Testing:**
   - Implement unit tests with mocked SDK responses
   - Add integration tests with actual API calls
   - Test error handling and edge cases

4. **Documentation:**
   - Document the transport interface
   - Provide examples for common use cases
   - Include troubleshooting information

## 8. Conclusion

Implementing an async SDK transport wrapper for OpenAI and Anthropic Python SDKs
is feasible using the adapter pattern to provide a consistent interface while
leveraging the specific features of each SDK. The key challenges are handling
streaming responses, translating SDK-specific errors, and exposing SDK features
consistently.

By following the recommendations in this report, pynector can create a robust
and flexible transport wrapper that conforms to the Transport protocol defined
in RR-1 and provides a consistent interface for both OpenAI and Anthropic SDKs.

## 9. References

1. OpenAI Python SDK GitHub Repository (search:
   exa-github.com/openai/openai-python)
2. Anthropic Python SDK GitHub Repository (search:
   exa-github.com/anthropics/anthropic-sdk-python)
3. OpenAI API Reference (search: exa-platform.openai.com/docs/api-reference)
4. Anthropic API Documentation (search: exa-docs.anthropic.com/en/api)
5. Anthropic API Errors Documentation (search:
   exa-docs.anthropic.com/en/api/errors)
6. OpenAI Python SDK Helpers (search:
   exa-github.com/openai/openai-python/blob/main/helpers.md)
7. Anthropic Streaming Messages Documentation (search:
   exa-docs.anthropic.com/en/api/messages-streaming)
8. Transport Abstraction Layers in Python (RR-1.md)
9. Structured Concurrency Patterns in AnyIO (RR-2.md)
10. OpenTelemetry Tracing and Structured Logging in Async Python Libraries
    (RR-3.md)
11. Implementing an Async HTTP Transport with httpx (RR-4.md)
