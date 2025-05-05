"""
Transport Abstraction Layer for pynector.

This package provides a flexible, maintainable, and type-safe interface for
network communication that follows the sans-I/O pattern.
"""

from pynector.transport.protocol import Transport, Message
from pynector.transport.factory import TransportFactory
from pynector.transport.registry import TransportFactoryRegistry
from pynector.transport.errors import (
    TransportError,
    ConnectionError,
    ConnectionTimeoutError,
    ConnectionRefusedError,
    MessageError,
    SerializationError,
    DeserializationError,
    TransportSpecificError,
)

__all__ = [
    'Transport',
    'Message',
    'TransportFactory',
    'TransportFactoryRegistry',
    'TransportError',
    'ConnectionError',
    'ConnectionTimeoutError',
    'ConnectionRefusedError',
    'MessageError',
    'SerializationError',
    'DeserializationError',
    'TransportSpecificError',
]