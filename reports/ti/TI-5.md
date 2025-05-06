# Test Implementation: SDK Transport Layer

**Issue:** #5\
**Author:** pynector-implementer\
**Date:** 2025-05-05\
**Status:** Draft

## 1. Introduction

This Test Implementation (TI) document outlines the testing strategy for the SDK
Transport Layer as specified in [TDS-5.md](../tds/TDS-5.md) and implemented
according to [IP-5.md](../ip/IP-5.md). The testing approach follows Test-Driven
Development (TDD) principles and aims to achieve >80% code coverage.

## 2. Test Structure

The tests will be organized in the following directory structure:

```
tests/
└── transport/
    └── sdk/
        ├── __init__.py
        ├── test_errors.py       # Tests for SDK-specific errors
        ├── test_adapter.py      # Tests for SDK adapters
        ├── test_transport.py    # Tests for SdkTransport
        ├── test_factory.py      # Tests for SdkTransportFactory
        └── test_integration.py  # Integration tests
```

## 3. Testing Framework and Tools

The tests will use the following tools:

- **pytest**: Primary testing framework
- **pytest-asyncio**: For testing async code
- **pytest-cov**: For measuring code coverage
- **pytest-mock**: For mocking dependencies

## 4. Test Cases

### 4.1 Error Tests (`test_errors.py`)

These tests will verify that the SDK-specific error hierarchy is correctly
implemented.

```python
import pytest
from pynector.transport.errors import TransportSpecificError
from pynector.transport.sdk.errors import (
    SdkTransportError,
    AuthenticationError,
    RateLimitError,
    InvalidRequestError,
    ResourceNotFoundError,
    PermissionError,
    RequestTooLargeError
)

def test_error_hierarchy():
    """Test that the error hierarchy is correctly implemented."""
    # Test inheritance
    assert issubclass(SdkTransportError, TransportSpecificError)
    assert issubclass(AuthenticationError, SdkTransportError)
    assert issubclass(RateLimitError, SdkTransportError)
    assert issubclass(InvalidRequestError, SdkTransportError)
    assert issubclass(ResourceNotFoundError, SdkTransportError)
    assert issubclass(PermissionError, SdkTransportError)
    assert issubclass(RequestTooLargeError, SdkTransportError)

    # Test instantiation
    error = SdkTransportError("Test error")
    assert str(error) == "Test error"

    # Test specific error types
    auth_error = AuthenticationError("Invalid API key")
    assert isinstance(auth_error, SdkTransportError)
    assert isinstance(auth_error, TransportSpecificError)
    assert str(auth_error) == "Invalid API key"

def test_error_handling():
    """Test error handling in a typical use case."""
    try:
        raise AuthenticationError("Invalid API key")
    except SdkTransportError as e:
        assert "Invalid API key" in str(e)
    except TransportSpecificError:
        pytest.fail("AuthenticationError should be caught by SdkTransportError")

    try:
        raise RateLimitError("Rate limit exceeded")
    except SdkTransportError as e:
        assert "Rate limit" in str(e)
    except TransportSpecificError:
        pytest.fail("RateLimitError should be caught by SdkTransportError")
```

### 4.2 Adapter Tests (`test_adapter.py`)

These tests will verify that the SDK adapters correctly implement the adapter
interface.

```python
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import AsyncIterator

from pynector.transport.sdk.adapter import SDKAdapter, OpenAIAdapter, AnthropicAdapter

# Test the abstract base class
def test_sdk_adapter_abstract():
    """Test that SDKAdapter is an abstract base class."""
    with pytest.raises(TypeError):
        SDKAdapter()  # Should raise TypeError because it's abstract

# Mock classes for testing
class MockOpenAIClient:
    def __init__(self):
        self.chat = MagicMock()
        self.chat.completions = MagicMock()
        self.chat.completions.create = AsyncMock()
        self.chat.completions.stream = AsyncMock()

class MockAnthropicClient:
    def __init__(self):
        self.messages = MagicMock()
        self.messages.create = AsyncMock()
        self.messages.create.with_streaming_response = AsyncMock()

# OpenAI adapter tests
@pytest.mark.asyncio
async def test_openai_adapter_complete():
    """Test OpenAI adapter complete method."""
    # Setup mock
    client = MockOpenAIClient()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Test response"
    client.chat.completions.create.return_value = mock_response

    # Create adapter
    adapter = OpenAIAdapter(client)

    # Test complete method
    result = await adapter.complete("Test prompt", model="gpt-4o")

    # Verify result
    assert result == "Test response"

    # Verify client was called correctly
    client.chat.completions.create.assert_called_once()
    call_args = client.chat.completions.create.call_args[1]
    assert call_args["messages"] == [{"role": "user", "content": "Test prompt"}]
    assert call_args["model"] == "gpt-4o"

@pytest.mark.asyncio
async def test_openai_adapter_stream():
    """Test OpenAI adapter stream method."""
    # Setup mock
    client = MockOpenAIClient()

    # Mock the stream context manager
    mock_stream = AsyncMock()
    mock_stream.__aenter__.return_value = mock_stream
    mock_stream.__aiter__.return_value = [
        MagicMock(type="content.delta", delta="Test "),
        MagicMock(type="content.delta", delta="response"),
        MagicMock(type="not.content.delta", delta="ignored")
    ]
    client.chat.completions.stream.return_value = mock_stream

    # Create adapter
    adapter = OpenAIAdapter(client)

    # Test stream method
    chunks = []
    async for chunk in adapter.stream("Test prompt", model="gpt-4o"):
        chunks.append(chunk)

    # Verify result
    assert chunks == [b"Test ", b"response"]

    # Verify client was called correctly
    client.chat.completions.stream.assert_called_once()
    call_args = client.chat.completions.stream.call_args[1]
    assert call_args["messages"] == [{"role": "user", "content": "Test prompt"}]
    assert call_args["model"] == "gpt-4o"

# Anthropic adapter tests
@pytest.mark.asyncio
async def test_anthropic_adapter_complete():
    """Test Anthropic adapter complete method."""
    # Setup mock
    client = MockAnthropicClient()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Test response")]
    client.messages.create.return_value = mock_response

    # Create adapter
    adapter = AnthropicAdapter(client)

    # Test complete method
    result = await adapter.complete("Test prompt", model="claude-3-opus-20240229")

    # Verify result
    assert result == "Test response"

    # Verify client was called correctly
    client.messages.create.assert_called_once()
    call_args = client.messages.create.call_args[1]
    assert call_args["messages"] == [{"role": "user", "content": "Test prompt"}]
    assert call_args["model"] == "claude-3-opus-20240229"

@pytest.mark.asyncio
async def test_anthropic_adapter_stream():
    """Test Anthropic adapter stream method."""
    # Setup mock
    client = MockAnthropicClient()

    # Mock the stream context manager
    mock_stream = AsyncMock()
    mock_stream.__aenter__.return_value = mock_stream
    mock_stream.iter_text = AsyncMock()
    mock_stream.iter_text.__aiter__.return_value = ["Test ", "response"]
    client.messages.create.with_streaming_response.return_value = mock_stream

    # Create adapter
    adapter = AnthropicAdapter(client)

    # Test stream method
    chunks = []
    async for chunk in adapter.stream("Test prompt", model="claude-3-opus-20240229"):
        chunks.append(chunk)

    # Verify result
    assert chunks == [b"Test ", b"response"]

    # Verify client was called correctly
    client.messages.create.with_streaming_response.assert_called_once()
    call_args = client.messages.create.with_streaming_response.call_args[1]
    assert call_args["messages"] == [{"role": "user", "content": "Test prompt"}]
    assert call_args["model"] == "claude-3-opus-20240229"
```

### 4.3 Transport Tests (`test_transport.py`)

These tests will verify that the `SdkTransport` class correctly implements the
Transport Protocol.

```python
import pytest
import os
import httpx
import openai
import anthropic
from unittest.mock import AsyncMock, MagicMock, patch

from pynector.transport.errors import ConnectionError, ConnectionTimeoutError, ConnectionRefusedError
from pynector.transport.sdk.errors import (
    SdkTransportError, AuthenticationError, RateLimitError,
    InvalidRequestError, ResourceNotFoundError, PermissionError,
    RequestTooLargeError
)
from pynector.transport.sdk.transport import SdkTransport
from pynector.transport.sdk.adapter import OpenAIAdapter, AnthropicAdapter

# Test initialization
def test_sdk_transport_init():
    """Test SdkTransport initialization."""
    # Default initialization
    transport = SdkTransport()
    assert transport.sdk_type == "openai"
    assert transport.api_key is None
    assert transport.base_url is None
    assert transport.timeout == 60.0
    assert transport.config == {}
    assert transport._client is None
    assert transport._adapter is None

    # Custom initialization
    transport = SdkTransport(
        sdk_type="anthropic",
        api_key="test-key",
        base_url="https://example.com",
        timeout=30.0,
        model="claude-3-opus-20240229"
    )
    assert transport.sdk_type == "anthropic"
    assert transport.api_key == "test-key"
    assert transport.base_url == "https://example.com"
    assert transport.timeout == 30.0
    assert transport.config == {"model": "claude-3-opus-20240229"}
    assert transport._client is None
    assert transport._adapter is None

# Test connect method
@pytest.mark.asyncio
async def test_sdk_transport_connect_openai():
    """Test SdkTransport connect method with OpenAI."""
    with patch("openai.AsyncOpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        transport = SdkTransport(sdk_type="openai", api_key="test-key")
        await transport.connect()

        # Verify client was created
        mock_openai.assert_called_once()
        assert transport._client is mock_client
        assert isinstance(transport._adapter, OpenAIAdapter)

@pytest.mark.asyncio
async def test_sdk_transport_connect_anthropic():
    """Test SdkTransport connect method with Anthropic."""
    with patch("anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        transport = SdkTransport(sdk_type="anthropic", api_key="test-key")
        await transport.connect()

        # Verify client was created
        mock_anthropic.assert_called_once()
        assert transport._client is mock_client
        assert isinstance(transport._adapter, AnthropicAdapter)

@pytest.mark.asyncio
async def test_sdk_transport_connect_unsupported():
    """Test SdkTransport connect method with unsupported SDK type."""
    transport = SdkTransport(sdk_type="unsupported")

    with pytest.raises(ValueError, match="Unsupported SDK type"):
        await transport.connect()

@pytest.mark.asyncio
async def test_sdk_transport_connect_error():
    """Test SdkTransport connect method with connection error."""
    with patch("openai.AsyncOpenAI") as mock_openai:
        mock_openai.side_effect = httpx.ConnectError("Connection refused")

        transport = SdkTransport(sdk_type="openai")

        with pytest.raises(ConnectionRefusedError, match="Connection refused"):
            await transport.connect()

# Test disconnect method
@pytest.mark.asyncio
async def test_sdk_transport_disconnect():
    """Test SdkTransport disconnect method."""
    with patch("openai.AsyncOpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        transport = SdkTransport(sdk_type="openai")
        await transport.connect()

        assert transport._client is not None
        assert transport._adapter is not None

        await transport.disconnect()

        assert transport._client is None
        assert transport._adapter is None

# Test send method
@pytest.mark.asyncio
async def test_sdk_transport_send():
    """Test SdkTransport send method."""
    # Setup mock adapter
    mock_adapter = MagicMock()
    mock_adapter.complete = AsyncMock()

    # Create transport with mock adapter
    transport = SdkTransport(sdk_type="openai", model="gpt-4o")
    transport._adapter = mock_adapter

    # Test send method
    await transport.send(b"Test prompt")

    # Verify adapter was called correctly
    mock_adapter.complete.assert_called_once_with("Test prompt", model="gpt-4o")

@pytest.mark.asyncio
async def test_sdk_transport_send_not_connected():
    """Test SdkTransport send method when not connected."""
    transport = SdkTransport()

    with pytest.raises(ConnectionError, match="not connected"):
        await transport.send(b"Test prompt")

@pytest.mark.asyncio
async def test_sdk_transport_send_error():
    """Test SdkTransport send method with error."""
    # Setup mock adapter
    mock_adapter = MagicMock()
    mock_adapter.complete = AsyncMock(side_effect=openai.AuthenticationError("Invalid API key"))

    # Create transport with mock adapter
    transport = SdkTransport(sdk_type="openai")
    transport._adapter = mock_adapter

    # Test send method
    with pytest.raises(AuthenticationError, match="Authentication failed"):
        await transport.send(b"Test prompt")

# Test receive method
@pytest.mark.asyncio
async def test_sdk_transport_receive():
    """Test SdkTransport receive method."""
    # Setup mock adapter
    mock_adapter = MagicMock()
    async def mock_stream(*args, **kwargs):
        yield b"Test "
        yield b"response"
    mock_adapter.stream = mock_stream

    # Create transport with mock adapter
    transport = SdkTransport(sdk_type="openai", prompt="Custom prompt", model="gpt-4o")
    transport._adapter = mock_adapter

    # Test receive method
    chunks = []
    async for chunk in transport.receive():
        chunks.append(chunk)

    # Verify result
    assert chunks == [b"Test ", b"response"]

@pytest.mark.asyncio
async def test_sdk_transport_receive_not_connected():
    """Test SdkTransport receive method when not connected."""
    transport = SdkTransport()

    with pytest.raises(ConnectionError, match="not connected"):
        async for _ in transport.receive():
            pass

@pytest.mark.asyncio
async def test_sdk_transport_receive_error():
    """Test SdkTransport receive method with error."""
    # Setup mock adapter
    mock_adapter = MagicMock()
    async def mock_stream(*args, **kwargs):
        raise openai.RateLimitError("Rate limit exceeded")
    mock_adapter.stream = mock_stream

    # Create transport with mock adapter
    transport = SdkTransport(sdk_type="openai")
    transport._adapter = mock_adapter

    # Test receive method
    with pytest.raises(RateLimitError, match="Rate limit exceeded"):
        async for _ in transport.receive():
            pass

# Test error translation
def test_sdk_transport_translate_error():
    """Test SdkTransport error translation."""
    transport = SdkTransport()

    # Test OpenAI errors
    assert isinstance(transport._translate_error(openai.AuthenticationError("test")), AuthenticationError)
    assert isinstance(transport._translate_error(openai.RateLimitError("test")), RateLimitError)
    assert isinstance(transport._translate_error(openai.APITimeoutError("test")), ConnectionTimeoutError)
    assert isinstance(transport._translate_error(openai.APIConnectionError("test")), ConnectionError)
    assert isinstance(transport._translate_error(openai.BadRequestError("test")), InvalidRequestError)
    assert isinstance(transport._translate_error(openai.NotFoundError("test")), ResourceNotFoundError)

    # Test Anthropic errors
    anthropic_401 = anthropic.APIStatusError("test", response=MagicMock(status_code=401))
    anthropic_401.status_code = 401
    assert isinstance(transport._translate_error(anthropic_401), AuthenticationError)

    anthropic_403 = anthropic.APIStatusError("test", response=MagicMock(status_code=403))
    anthropic_403.status_code = 403
    assert isinstance(transport._translate_error(anthropic_403), PermissionError)

    anthropic_404 = anthropic.APIStatusError("test", response=MagicMock(status_code=404))
    anthropic_404.status_code = 404
    assert isinstance(transport._translate_error(anthropic_404), ResourceNotFoundError)

    anthropic_429 = anthropic.APIStatusError("test", response=MagicMock(status_code=429))
    anthropic_429.status_code = 429
    assert isinstance(transport._translate_error(anthropic_429), RateLimitError)

    # Test httpx errors
    assert isinstance(transport._translate_error(httpx.TimeoutException("test")), ConnectionTimeoutError)
    assert isinstance(transport._translate_error(httpx.ConnectError("test")), ConnectionRefusedError)
    assert isinstance(transport._translate_error(httpx.RequestError("test")), ConnectionError)

    # Test default case
    assert isinstance(transport._translate_error(Exception("test")), SdkTransportError)

# Test async context manager
@pytest.mark.asyncio
async def test_sdk_transport_context_manager():
    """Test SdkTransport async context manager."""
    with patch.object(SdkTransport, "connect", AsyncMock()) as mock_connect:
        with patch.object(SdkTransport, "disconnect", AsyncMock()) as mock_disconnect:
            transport = SdkTransport()

            async with transport as t:
                assert t is transport
                mock_connect.assert_called_once()
                mock_disconnect.assert_not_called()

            mock_disconnect.assert_called_once()
```

### 4.4 Factory Tests (`test_factory.py`)

These tests will verify that the `SdkTransportFactory` correctly creates
`SdkTransport` instances.

```python
import pytest
from unittest.mock import patch

from pynector.transport.sdk.factory import SdkTransportFactory
from pynector.transport.sdk.transport import SdkTransport

def test_sdk_transport_factory_init():
    """Test SdkTransportFactory initialization."""
    # Default initialization
    factory = SdkTransportFactory()
    assert factory.sdk_type == "openai"
    assert factory.api_key is None
    assert factory.base_url is None
    assert factory.timeout == 60.0
    assert factory.default_config == {}

    # Custom initialization
    factory = SdkTransportFactory(
        sdk_type="anthropic",
        api_key="test-key",
        base_url="https://example.com",
        timeout=30.0,
        model="claude-3-opus-20240229"
    )
    assert factory.sdk_type == "anthropic"
    assert factory.api_key == "test-key"
    assert factory.base_url == "https://example.com"
    assert factory.timeout == 30.0
    assert factory.default_config == {"model": "claude-3-opus-20240229"}

def test_sdk_transport_factory_create_transport():
    """Test SdkTransportFactory create_transport method."""
    with patch("pynector.transport.sdk.transport.SdkTransport") as mock_transport:
        # Create factory
        factory = SdkTransportFactory(
            sdk_type="openai",
            api_key="default-key",
            timeout=60.0,
            model="gpt-3.5-turbo"
        )

        # Create transport with default settings
        factory.create_transport()

        # Verify transport was created with correct settings
        mock_transport.assert_called_once_with(
            sdk_type="openai",
            api_key="default-key",
            base_url=None,
            timeout=60.0,
            model="gpt-3.5-turbo"
        )

        mock_transport.reset_mock()

        # Create transport with custom settings
        factory.create_transport(
            sdk_type="anthropic",
            api_key="custom-key",
            base_url="https://example.com",
            timeout=30.0,
            model="claude-3-opus-20240229"
        )

        # Verify transport was created with correct settings
        mock_transport.assert_called_once_with(
            sdk_type="anthropic",
            api_key="custom-key",
            base_url="https://example.com",
            timeout=30.0,
            model="claude-3-opus-20240229"
        )

def test_sdk_transport_factory_create_transport_merge_config():
    """Test SdkTransportFactory create_transport method with merged config."""
    with patch("pynector.transport.sdk.transport.SdkTransport") as mock_transport:
        # Create factory with default config
        factory = SdkTransportFactory(
            sdk_type="openai",
            model="gpt-3.5-turbo",
            temperature=0.7,
            max_tokens=100
        )

        # Create transport with partial override
        factory.create_transport(
            model="gpt-4o",
            max_tokens=200
        )

        # Verify transport was created with merged config
        call_kwargs = mock_transport.call_args[1]
        assert call_kwargs["sdk_type"] == "openai"
        assert call_kwargs["model"] == "gpt-4o"  # Overridden
        assert call_kwargs["temperature"] == 0.7  # From default
        assert call_kwargs["max_tokens"] == 200  # Overridden
```

### 4.5 Integration Tests (`test_integration.py`)

These tests will verify that the SDK Transport components work together
correctly.

```python
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from pynector.transport.registry import TransportFactoryRegistry
from pynector.transport.sdk.factory import SdkTransportFactory
from pynector.transport.sdk.transport import SdkTransport
from pynector.transport.sdk.adapter import OpenAIAdapter, AnthropicAdapter

@pytest.mark.asyncio
async def test_sdk_transport_with_registry():
    """Test SdkTransport integration with TransportFactoryRegistry."""
    # Create registry
    registry = TransportFactoryRegistry()

    # Register SDK transport factories
    registry.register("openai", SdkTransportFactory(sdk_type="openai"))
    registry.register("anthropic", SdkTransportFactory(sdk_type="anthropic"))

    # Create transports using the registry
    with patch("openai.AsyncOpenAI") as mock_openai:
        with patch("anthropic.AsyncAnthropic") as mock_anthropic:
            # Mock clients
            mock_openai_client = MagicMock()
            mock_anthropic_client = MagicMock()
            mock_openai.return_value = mock_openai_client
            mock_anthropic.return_value = mock_anthropic_client

            # Create transports
            openai_transport = registry.create_transport("openai", model="gpt-4o")
            anthropic_transport = registry.create_transport("anthropic", model="claude-3-opus-20240229")

            # Verify transports were created correctly
            assert isinstance(openai_transport, SdkTransport)
            assert openai_transport.sdk_type == "openai"
            assert openai_transport.config["model"] == "gpt-4o"

            assert isinstance(anthropic_transport, SdkTransport)
            assert anthropic_transport.sdk_type == "anthropic"
            assert anthropic_transport.config["model"] == "claude-3-opus-20240229"

@pytest.mark.asyncio
async def test_sdk_transport_end_to_end():
    """Test SdkTransport end-to-end flow."""
    # Setup mocks
    mock_adapter = MagicMock()
    mock_adapter.complete = AsyncMock(return_value="Test response")

    async def mock_stream(*args, **kwargs):
        yield b"Test "
        yield b"response"
    mock_adapter.stream = mock_stream

    # Create transport with mock adapter
    transport = SdkTransport(sdk_type="openai", model="gpt-4o")

    # Mock connect to set the adapter
    original_connect = transport.connect
    async def mock_connect():
        await original_connect()
        transport._adapter = mock_adapter
    transport.connect = mock_connect

    # Test end-to-end flow
    async with transport as t:
        # Test send
        await t.send(b"Test prompt")
        mock_adapter.complete.assert_called_once_with("Test prompt", model="gpt-4o")

        # Test receive
        chunks = []
        async for chunk in t.receive():
            chunks.append(chunk)
        assert chunks == [b"Test ", b"response"]

@pytest.mark.asyncio
async def test_mock_adapter_for_testing():
    """Test the mock adapter pattern described in TDS-5.md."""
    # Create a mock adapter for testing
    class MockAdapter(MagicMock):
        async def complete(self, prompt, **kwargs):
            if prompt == "error":
                raise ValueError("Test error")
            return f"Response to: {prompt}"

        async def stream(self, prompt, **kwargs):
            if prompt == "error":
                raise ValueError("Test error")
            words = f"Response to: {prompt}".split()
            for word in words:
                yield word.encode("utf-8")

    # Create transport with mock adapter
    transport = SdkTransport(sdk_type="mock", prompt="Test prompt")
    transport._adapter = MockAdapter()

    # Test send
    await transport.send(b"Hello")
    transport._adapter.complete.assert_called_once()

    # Test receive
    chunks = []
    async for chunk in transport.receive():
        chunks.append(chunk.decode("utf-8"))

    assert "".join(chunks) == "Response to: Test prompt"

    # Test error handling
    with pytest.raises(SdkTransportError):
        await transport.send(b"error")
```

### 4.6 Mock Adapter for Testing

As described in TDS-5.md, we'll implement a mock adapter for testing:

```python
# In tests/transport/sdk/conftest.py
import pytest
import asyncio
from typing import Dict, Any, AsyncIterator, Optional
from unittest.mock import MagicMock

from pynector.transport.sdk.adapter import SDKAdapter

class MockAdapter(SDKAdapter):
    """Mock adapter for testing."""

    def __init__(self, responses: Dict[str, Any] = None, errors: Dict[str, Exception] = None):
        """Initialize the mock adapter with responses and errors.

        Args:
            responses: Mapping of prompts to responses.
            errors: Mapping of prompts to errors.
        """
        self.responses = responses or {}
        self.errors = errors or {}
        self.complete_calls = []
        self.stream_calls = []

    async def complete(self, prompt: str, model: Optional[str] = None, **kwargs: Any) -> str:
        """Generate a completion for the given prompt."""
        self.complete_calls.append((prompt, model, kwargs))

        if prompt in self.errors:
            raise self.errors[prompt]

        return self.responses.get(prompt, f"Mock response to: {prompt}")

    async def stream(self, prompt: str, model: Optional[str] = None, **kwargs: Any) -> AsyncIterator[bytes]:
        """Stream a completion for the given prompt."""
        self.stream_calls.append((prompt, model, kwargs))

        if prompt in self.errors:
            raise self.errors[prompt]

        response = self.responses.get(prompt, f"Mock response to: {prompt}")
        chunks = response.split()

        for chunk in chunks:
            yield chunk.encode("utf-8")
            await asyncio.sleep(0.01)  # Simulate streaming delay

@pytest.fixture
def mock_adapter():
    """Fixture for creating a mock adapter."""
    return MockAdapter(
        responses={
            "hello": "Hello, world!",
            "test": "This is a test response."
        },
        errors={
            "error": ValueError("Test error"),
            "auth_error": Exception("Authentication failed")
        }
    )

@pytest.fixture
def mock_transport(mock_adapter):
    """Fixture for creating a transport with a mock adapter."""
    from pynector.transport.sdk.transport import SdkTransport

    transport = SdkTransport(sdk_type="mock")
    transport._adapter = mock_adapter

    return transport
```

## 5. Test Coverage

The tests are designed to achieve >80% code coverage across all components.
Coverage will be measured using pytest-cov and reported during CI runs.

```bash
pytest --cov=pynector.transport.sdk tests/transport/sdk/
```

## 6. Test Execution

Tests will be executed as part of the CI pipeline and can also be run locally
using pytest:

```bash
# Run all tests
pytest tests/transport/sdk/

# Run specific test file
pytest tests/transport/sdk/test_transport.py

# Run with coverage
pytest --cov=pynector.transport.sdk tests/transport/sdk/

# Generate coverage report
pytest --cov=pynector.transport.sdk --cov-report=html tests/transport/sdk/
```

## 7. References

1. Technical Design Specification: SDK Transport Layer (TDS-5.md) (search:
   internal-document)
2. Technical Design Specification: Transport Abstraction Layer (TDS-1.md)
   (search: internal-document)
3. Implementation Plan: SDK Transport Layer (IP-5.md) (search:
   internal-document)
4. Research Report: Async SDK Transport Wrapper for OpenAI and Anthropic
   (RR-5.md) (search: internal-document)
5. OpenAI Python SDK GitHub Repository (search:
   exa-github.com/openai/openai-python)
6. Anthropic Python SDK GitHub Repository (search:
   exa-github.com/anthropics/anthropic-sdk-python)
7. pytest Documentation (search: exa-docs.pytest.org)
8. pytest-asyncio Documentation (search: exa-pytest-asyncio.readthedocs.io)
9. pytest-mock Documentation (search: exa-pytest-mock.readthedocs.io)
