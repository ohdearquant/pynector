"""
Transport Abstraction Layer for pynector.

This package provides a flexible, maintainable, and type-safe interface for
network communication that follows the sans-I/O pattern.
"""

from pynector.transport.errors import (
    ConnectionError,
    ConnectionRefusedError,
    ConnectionTimeoutError,
    DeserializationError,
    MessageError,
    SerializationError,
    TransportError,
    TransportSpecificError,
)
from pynector.transport.factory import TransportFactory
from pynector.transport.protocol import Message, Transport
from pynector.transport.registry import TransportFactoryRegistry

__all__ = [
    "Transport",
    "Message",
    "TransportFactory",
    "TransportFactoryRegistry",
    "TransportError",
    "ConnectionError",
    "ConnectionTimeoutError",
    "ConnectionRefusedError",
    "MessageError",
    "SerializationError",
    "DeserializationError",
    "TransportSpecificError",
]
