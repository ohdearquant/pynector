"""
Pytest configuration for pynector tests.

This module contains fixtures and configuration for pytest.
"""

# We don't need to define our own event_loop fixture as pytest-asyncio provides one
# This was causing a deprecation warning
