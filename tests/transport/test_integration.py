"""
Integration tests for the Transport Abstraction Layer.

This module contains integration tests for the Transport Abstraction Layer components.
"""

import pytest

from pynector.transport.errors import ConnectionError
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


@pytest.mark.asyncio
async def test_transport_error_handling():
    """Test error handling in transport integration."""
    # Set up registry
    registry = TransportFactoryRegistry()
    registry.register("json", MockJsonTransportFactory())

    # Create transport
    transport = registry.create_transport("json")

    # Test sending without connecting
    with pytest.raises(ConnectionError, match="Not connected"):
        await transport.send(JsonMessage({}, {}))

    # Test receiving without connecting
    with pytest.raises(ConnectionError, match="Not connected"):
        async for _ in transport.receive():
            pass


@pytest.mark.asyncio
async def test_multiple_transports():
    """Test using multiple transports."""
    # Set up registry
    registry = TransportFactoryRegistry()
    registry.register("json", MockJsonTransportFactory())

    # Create messages for each transport
    messages1 = [JsonMessage({"id": "1"}, {"data": "transport1"})]
    messages2 = [JsonMessage({"id": "2"}, {"data": "transport2"})]

    # Create transports
    transport1 = registry.create_transport("json", messages=messages1)
    transport2 = registry.create_transport("json", messages=messages2)

    # Use both transports
    async with transport1 as t1, transport2 as t2:
        # Send to both
        await t1.send(JsonMessage({"id": "3"}, {"data": "to-transport1"}))
        await t2.send(JsonMessage({"id": "4"}, {"data": "to-transport2"}))

        # Receive from both
        received1 = [msg async for msg in t1.receive()]
        received2 = [msg async for msg in t2.receive()]

        assert len(received1) == 1
        assert received1[0].get_payload()["data"] == "transport1"

        assert len(received2) == 1
        assert received2[0].get_payload()["data"] == "transport2"

        # Verify sent messages
        assert len(t1.sent_messages) == 1
        assert t1.sent_messages[0].get_payload()["data"] == "to-transport1"

        assert len(t2.sent_messages) == 1
        assert t2.sent_messages[0].get_payload()["data"] == "to-transport2"

    # Verify both disconnected
    assert not transport1.connected
    assert not transport2.connected


@pytest.mark.asyncio
async def test_transport_context_manager_error_handling():
    """Test error handling in transport context manager."""

    class ErrorTransport(MockJsonTransport):
        async def connect(self) -> None:
            raise ConnectionError("Failed to connect")

    class ErrorTransportFactory:
        def create_transport(self, **kwargs):
            return ErrorTransport()

    # Set up registry
    registry = TransportFactoryRegistry()
    registry.register("error", ErrorTransportFactory())

    # Test context manager with connection error
    with pytest.raises(ConnectionError, match="Failed to connect"):
        async with registry.create_transport("error") as _:
            pass  # Should not reach here
