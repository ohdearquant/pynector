# Implementation Plan: SDK Transport Layer

**Issue:** #5\
**Author:** pynector-implementer\
**Date:** 2025-05-05\
**Status:** Draft

## 1. Introduction

This Implementation Plan (IP) outlines the approach for implementing the SDK
Transport Layer as specified in [TDS-5.md](../tds/TDS-5.md). The implementation
will provide a unified interface for interacting with AI model provider SDKs
(OpenAI and Anthropic) while conforming to the Transport Protocol defined in
[TDS-1.md](../tds/TDS-1.md).

## 2. Project Structure

The SDK Transport Layer will be implemented in the following directory
structure:

```
pynector/
├── transport/
│   ├── __init__.py
│   ├── protocol.py       # Transport Protocol (already implemented)
│   ├── errors.py         # Error hierarchy (already implemented)
│   ├── sdk/
│   │   ├── __init__.py
│   │   ├── errors.py     # SDK-specific error classes
│   │   ├── transport.py  # SdkTransport implementation
│   │   ├── adapter.py    # SDK adapter implementations
│   │   └── factory.py    # SdkTransportFactory implementation
└── tests/
    └── transport/
        └── sdk/
            ├── __init__.py
            ├── test_errors.py
            ├── test_transport.py
            ├── test_adapter.py
            ├── test_factory.py
            └── test_integration.py
```

## 3. Implementation Details

### 3.1 SDK Transport Errors (`sdk/errors.py`)

The SDK Transport Layer will extend the error hierarchy defined in
`transport/errors.py` with SDK-specific errors:

```python
from pynector.transport.errors import TransportSpecificError

class SdkTransportError(TransportSpecificError):
    """Base class for all SDK transport errors."""
    pass

class AuthenticationError(SdkTransportError):
    """Error indicating an authentication failure."""
    pass

class RateLimitError(SdkTransportError):
    """Error indicating a rate limit was exceeded."""
    pass

class InvalidRequestError(SdkTransportError):
    """Error indicating an invalid request."""
    pass

class ResourceNotFoundError(SdkTransportError):
    """Error indicating a resource was not found."""
    pass

class PermissionError(SdkTransportError):
    """Error indicating a permission issue."""
    pass

class RequestTooLargeError(SdkTransportError):
    """Error indicating a request was too large."""
    pass
```

### 3.2 SDK Adapter Interface (`sdk/adapter.py`)

The SDK adapter interface will define the common interface for all SDK-specific
adapters:

```python
from typing import AsyncIterator, Dict, Any, Optional, Type
import abc

class SDKAdapter(abc.ABC):
    """Base adapter class for SDK-specific implementations."""

    @abc.abstractmethod
    async def complete(self, prompt: str, model: Optional[str] = None, **kwargs: Any) -> str:
        """Generate a completion for the given prompt.

        Args:
            prompt: The prompt to complete.
            model: The model to use.
            **kwargs: Additional model-specific parameters.

        Returns:
            The completion text.

        Raises:
            Exception: If the completion fails.
        """
        pass

    @abc.abstractmethod
    async def stream(self, prompt: str, model: Optional[str] = None, **kwargs: Any) -> AsyncIterator[bytes]:
        """Stream a completion for the given prompt.

        Args:
            prompt: The prompt to complete.
            model: The model to use.
            **kwargs: Additional model-specific parameters.

        Returns:
            An async iterator yielding completion chunks as bytes.

        Raises:
            Exception: If the streaming fails.
        """
        pass
```

### 3.3 OpenAI Adapter Implementation (`sdk/adapter.py`)

The OpenAI adapter will implement the SDK adapter interface for the OpenAI SDK:

```python
import openai
from typing import AsyncIterator, Dict, Any, Optional

class OpenAIAdapter(SDKAdapter):
    """Adapter for the OpenAI SDK."""

    def __init__(self, client: openai.AsyncOpenAI):
        """Initialize the adapter with an OpenAI client.

        Args:
            client: The OpenAI client.
        """
        self.client = client

    async def complete(self, prompt: str, model: Optional[str] = None, **kwargs: Any) -> str:
        """Generate a completion using the OpenAI API.

        Args:
            prompt: The prompt to complete.
            model: The model to use. Defaults to "gpt-3.5-turbo".
            **kwargs: Additional parameters for the completion API.

        Returns:
            The completion text.
        """
        messages = [{"role": "user", "content": prompt}]
        response = await self.client.chat.completions.create(
            messages=messages,
            model=model or "gpt-3.5-turbo",
            **kwargs
        )
        return response.choices[0].message.content

    async def stream(self, prompt: str, model: Optional[str] = None, **kwargs: Any) -> AsyncIterator[bytes]:
        """Stream a completion using the OpenAI API.

        Args:
            prompt: The prompt to complete.
            model: The model to use. Defaults to "gpt-3.5-turbo".
            **kwargs: Additional parameters for the completion API.

        Returns:
            An async iterator yielding completion chunks as bytes.
        """
        messages = [{"role": "user", "content": prompt}]
        async with self.client.chat.completions.stream(
            messages=messages,
            model=model or "gpt-3.5-turbo",
            **kwargs
        ) as stream:
            async for event in stream:
                if event.type == "content.delta":
                    yield event.delta.encode("utf-8")
```

### 3.4 Anthropic Adapter Implementation (`sdk/adapter.py`)

The Anthropic adapter will implement the SDK adapter interface for the Anthropic
SDK:

```python
import anthropic
from typing import AsyncIterator, Dict, Any, Optional

class AnthropicAdapter(SDKAdapter):
    """Adapter for the Anthropic SDK."""

    def __init__(self, client: anthropic.AsyncAnthropic):
        """Initialize the adapter with an Anthropic client.

        Args:
            client: The Anthropic client.
        """
        self.client = client

    async def complete(self, prompt: str, model: Optional[str] = None, **kwargs: Any) -> str:
        """Generate a completion using the Anthropic API.

        Args:
            prompt: The prompt to complete.
            model: The model to use. Defaults to "claude-3-sonnet-20240229".
            **kwargs: Additional parameters for the completion API.

        Returns:
            The completion text.
        """
        response = await self.client.messages.create(
            messages=[{"role": "user", "content": prompt}],
            model=model or "claude-3-sonnet-20240229",
            **kwargs
        )
        return response.content[0].text

    async def stream(self, prompt: str, model: Optional[str] = None, **kwargs: Any) -> AsyncIterator[bytes]:
        """Stream a completion using the Anthropic API.

        Args:
            prompt: The prompt to complete.
            model: The model to use. Defaults to "claude-3-sonnet-20240229".
            **kwargs: Additional parameters for the completion API.

        Returns:
            An async iterator yielding completion chunks as bytes.
        """
        async with self.client.messages.create.with_streaming_response(
            messages=[{"role": "user", "content": prompt}],
            model=model or "claude-3-sonnet-20240229",
            **kwargs
        ) as response:
            async for chunk in response.iter_text():
                yield chunk.encode("utf-8")
```

### 3.5 SdkTransport Implementation (`sdk/transport.py`)

The `SdkTransport` class will implement the Transport Protocol defined in
`transport/protocol.py`:

```python
from typing import AsyncIterator, Dict, Any, Optional, Union, Type
import os
import httpx
import openai
import anthropic
from contextlib import asynccontextmanager

from pynector.transport.errors import (
    TransportError, ConnectionError, ConnectionTimeoutError,
    ConnectionRefusedError, MessageError, SerializationError,
    DeserializationError, TransportSpecificError
)
from pynector.transport.sdk.errors import (
    SdkTransportError, AuthenticationError, RateLimitError,
    InvalidRequestError, ResourceNotFoundError, PermissionError,
    RequestTooLargeError
)
from pynector.transport.sdk.adapter import SDKAdapter, OpenAIAdapter, AnthropicAdapter

class SdkTransport:
    """SDK transport implementation using OpenAI and Anthropic SDKs."""

    def __init__(
        self,
        sdk_type: str = "openai",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
        **kwargs: Any
    ):
        """Initialize the transport with configuration options.

        Args:
            sdk_type: The SDK type to use. Can be "openai" or "anthropic".
            api_key: The API key to use. If not provided, will use environment variables.
            base_url: The base URL to use. If not provided, will use the default.
            timeout: The timeout in seconds for API calls.
            **kwargs: Additional SDK-specific configuration options.
        """
        self.sdk_type = sdk_type
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.config = kwargs
        self._client = None
        self._adapter = None

    async def connect(self) -> None:
        """Establish the connection to the SDK.

        Raises:
            ConnectionError: If the connection cannot be established.
            TimeoutError: If the connection attempt times out.
        """
        if self._client is not None:
            return

        try:
            if self.sdk_type == "openai":
                self._client = await self._create_openai_client()
                self._adapter = OpenAIAdapter(self._client)
            elif self.sdk_type == "anthropic":
                self._client = await self._create_anthropic_client()
                self._adapter = AnthropicAdapter(self._client)
            else:
                raise ValueError(f"Unsupported SDK type: {self.sdk_type}")
        except Exception as e:
            raise self._translate_connection_error(e)

    async def disconnect(self) -> None:
        """Close the connection to the SDK."""
        self._client = None
        self._adapter = None

    async def send(self, data: bytes) -> None:
        """Send data over the transport.

        Args:
            data: The data to send.

        Raises:
            ConnectionError: If the connection is closed or broken.
            TransportError: For other transport-specific errors.
        """
        if self._adapter is None:
            raise ConnectionError("Transport not connected")

        try:
            prompt = data.decode("utf-8")
            model = self.config.get("model")
            kwargs = {k: v for k, v in self.config.items() if k != "model"}
            await self._adapter.complete(prompt, model=model, **kwargs)
        except Exception as e:
            raise self._translate_error(e)

    async def receive(self) -> AsyncIterator[bytes]:
        """Receive data from the transport.

        Returns:
            An async iterator yielding data as it is received.

        Raises:
            ConnectionError: If the connection is closed or broken.
            TransportError: For other transport-specific errors.
        """
        if self._adapter is None:
            raise ConnectionError("Transport not connected")

        try:
            prompt = self.config.get("prompt", "Generate a response")
            model = self.config.get("model")
            kwargs = {k: v for k, v in self.config.items() if k not in ["prompt", "model"]}
            async for chunk in self._adapter.stream(prompt, model=model, **kwargs):
                yield chunk
        except Exception as e:
            raise self._translate_error(e)

    async def _create_openai_client(self) -> openai.AsyncOpenAI:
        """Create an OpenAI client.

        Returns:
            The OpenAI client.

        Raises:
            ConnectionError: If the client cannot be created.
        """
        try:
            return openai.AsyncOpenAI(
                api_key=self.api_key or os.environ.get("OPENAI_API_KEY"),
                base_url=self.base_url,
                timeout=self.timeout,
                **{k: v for k, v in self.config.items() if k in ["organization", "max_retries"]}
            )
        except Exception as e:
            raise ConnectionError(f"Failed to create OpenAI client: {str(e)}")

    async def _create_anthropic_client(self) -> anthropic.AsyncAnthropic:
        """Create an Anthropic client.

        Returns:
            The Anthropic client.

        Raises:
            ConnectionError: If the client cannot be created.
        """
        try:
            return anthropic.AsyncAnthropic(
                api_key=self.api_key or os.environ.get("ANTHROPIC_API_KEY"),
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                **{k: v for k, v in self.config.items() if k in ["auth_token"]}
            )
        except Exception as e:
            raise ConnectionError(f"Failed to create Anthropic client: {str(e)}")

    def _translate_connection_error(self, error: Exception) -> Exception:
        """Translate SDK connection errors to Transport errors.

        Args:
            error: The SDK error.

        Returns:
            The translated error.
        """
        if isinstance(error, httpx.TimeoutException):
            return ConnectionTimeoutError(f"Connection timeout: {str(error)}")
        elif isinstance(error, httpx.ConnectError):
            return ConnectionRefusedError(f"Connection refused: {str(error)}")
        else:
            return ConnectionError(f"Connection error: {str(error)}")

    def _translate_error(self, error: Exception) -> Exception:
        """Translate SDK errors to Transport errors.

        Args:
            error: The SDK error.

        Returns:
            The translated error.
        """
        # OpenAI errors
        if isinstance(error, openai.AuthenticationError):
            return AuthenticationError(f"Authentication failed: {str(error)}")
        elif isinstance(error, openai.RateLimitError):
            return RateLimitError(f"Rate limit exceeded: {str(error)}")
        elif isinstance(error, openai.APITimeoutError):
            return ConnectionTimeoutError(f"API timeout: {str(error)}")
        elif isinstance(error, openai.APIConnectionError):
            return ConnectionError(f"API connection error: {str(error)}")
        elif isinstance(error, openai.BadRequestError):
            return InvalidRequestError(f"Bad request: {str(error)}")
        elif isinstance(error, openai.NotFoundError):
            return ResourceNotFoundError(f"Resource not found: {str(error)}")

        # Anthropic errors
        elif isinstance(error, anthropic.APIStatusError):
            status_code = getattr(error, "status_code", None)
            if status_code == 401:
                return AuthenticationError(f"Authentication failed: {str(error)}")
            elif status_code == 403:
                return PermissionError(f"Permission denied: {str(error)}")
            elif status_code == 404:
                return ResourceNotFoundError(f"Resource not found: {str(error)}")
            elif status_code == 429:
                return RateLimitError(f"Rate limit exceeded: {str(error)}")
            elif status_code == 400:
                return InvalidRequestError(f"Bad request: {str(error)}")
            elif status_code == 413:
                return RequestTooLargeError(f"Request too large: {str(error)}")

        # httpx errors
        elif isinstance(error, httpx.TimeoutException):
            return ConnectionTimeoutError(f"Connection timeout: {str(error)}")
        elif isinstance(error, httpx.ConnectError):
            return ConnectionRefusedError(f"Connection refused: {str(error)}")
        elif isinstance(error, httpx.RequestError):
            return ConnectionError(f"Request error: {str(error)}")

        # Default case
        return SdkTransportError(f"SDK error: {str(error)}")

    async def __aenter__(self) -> 'SdkTransport':
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

### 3.6 SdkTransportFactory Implementation (`sdk/factory.py`)

The `SdkTransportFactory` will implement the `TransportFactory` protocol:

```python
from typing import Dict, Any, Optional
from pynector.transport.sdk.transport import SdkTransport

class SdkTransportFactory:
    """Factory for creating SDK transport instances."""

    def __init__(
        self,
        sdk_type: str = "openai",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
        **kwargs: Any
    ):
        """Initialize the factory with default configuration options.

        Args:
            sdk_type: The SDK type to use. Can be "openai" or "anthropic".
            api_key: The API key to use. If not provided, will use environment variables.
            base_url: The base URL to use. If not provided, will use the default.
            timeout: The timeout in seconds for API calls.
            **kwargs: Additional SDK-specific configuration options.
        """
        self.sdk_type = sdk_type
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.default_config = kwargs

    def create_transport(self, **kwargs: Any) -> SdkTransport:
        """Create a new SDK transport instance.

        Args:
            **kwargs: Additional configuration options that override the defaults.

        Returns:
            A new SDK transport instance.

        Raises:
            ValueError: If the configuration is invalid.
        """
        # Merge kwargs with default_config, with kwargs taking precedence
        config = {**self.default_config, **kwargs}

        return SdkTransport(
            sdk_type=kwargs.get("sdk_type", self.sdk_type),
            api_key=kwargs.get("api_key", self.api_key),
            base_url=kwargs.get("base_url", self.base_url),
            timeout=kwargs.get("timeout", self.timeout),
            **config
        )
```

### 3.7 Integration with TransportFactoryRegistry

The SDK Transport will be integrated with the existing
`TransportFactoryRegistry` by registering the `SdkTransportFactory`:

```python
# Example usage in application code
from pynector.transport.registry import TransportFactoryRegistry
from pynector.transport.sdk.factory import SdkTransportFactory

registry = TransportFactoryRegistry()
registry.register("openai", SdkTransportFactory(sdk_type="openai"))
registry.register("anthropic", SdkTransportFactory(sdk_type="anthropic"))

# Create a transport using the registry
transport = registry.create_transport("openai", model="gpt-4o")
```

## 4. Implementation Approach

The implementation will follow these steps:

1. **Set up project structure:** Create the necessary directories and files
2. **Implement error classes:** Implement the SDK-specific error classes
3. **Implement adapter interface:** Implement the `SDKAdapter` abstract base
   class
4. **Implement OpenAI adapter:** Implement the `OpenAIAdapter` class
5. **Implement Anthropic adapter:** Implement the `AnthropicAdapter` class
6. **Implement SdkTransport:** Implement the `SdkTransport` class
7. **Implement SdkTransportFactory:** Implement the `SdkTransportFactory` class
8. **Write tests:** Write comprehensive tests for all components
9. **Documentation:** Add docstrings and type hints to all components

## 5. Dependencies

The implementation will require the following dependencies:

- Python 3.9 or higher (as specified in pyproject.toml)
- Standard library modules:
  - `typing` for type hints
  - `os` for environment variable access
  - `contextlib` for async context management
  - `abc` for abstract base classes
- External dependencies:
  - `openai` for the OpenAI SDK
  - `anthropic` for the Anthropic SDK
  - `httpx` for HTTP client functionality (used by both SDKs)

These dependencies will need to be added to the project's `pyproject.toml` file.

## 6. Testing Strategy

The testing strategy is detailed in the Test Implementation document (TI-5.md).
It will include:

- Unit tests for all components
- Integration tests for component interactions
- Mock adapters for testing without API calls
- Tests for error translation
- Tests for streaming functionality

## 7. References

1. Technical Design Specification: SDK Transport Layer (TDS-5.md) (search:
   internal-document)
2. Technical Design Specification: Transport Abstraction Layer (TDS-1.md)
   (search: internal-document)
3. Research Report: Async SDK Transport Wrapper for OpenAI and Anthropic
   (RR-5.md) (search: internal-document)
4. OpenAI Python SDK GitHub Repository (search:
   exa-github.com/openai/openai-python)
5. Anthropic Python SDK GitHub Repository (search:
   exa-github.com/anthropics/anthropic-sdk-python)
6. OpenAI API Reference (search: exa-platform.openai.com/docs/api-reference)
7. Anthropic API Documentation (search: exa-docs.anthropic.com/en/api)
8. Python Adapter Pattern (search:
   exa-refactoring.guru/design-patterns/adapter/python/example)
