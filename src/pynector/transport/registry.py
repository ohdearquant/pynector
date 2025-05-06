"""
Registry for transport factories.

This module provides a registry for transport factories, allowing for
dynamic registration and lookup of transport factories.
"""

from typing import Any

from pynector.transport.factory import TransportFactory
from pynector.transport.protocol import Transport


class TransportFactoryRegistry:
    """Registry for transport factories."""

    def __init__(self):
        """Initialize a new transport factory registry."""
        self._factories = {}

    def register(self, name: str, factory: TransportFactory) -> None:
        """Register a transport factory.

        Args:
            name: The name to register the factory under.
            factory: The factory instance.
        """
        self._factories[name] = factory

    def get(self, name: str) -> TransportFactory:
        """Get a transport factory by name.

        Args:
            name: The name of the factory to get.

        Returns:
            The factory instance.

        Raises:
            KeyError: If no factory is registered with the given name.
        """
        return self._factories[name]

    def create_transport(self, name: str, **kwargs: Any) -> Transport:
        """Create a transport using a registered factory.

        Args:
            name: The name of the factory to use.
            **kwargs: Transport-specific configuration options.

        Returns:
            A new transport instance.

        Raises:
            KeyError: If no factory is registered with the given name.
        """
        factory = self.get(name)
        return factory.create_transport(**kwargs)
