"""
Pytest configuration for pynector tests.

This module contains fixtures and configuration for pytest.
"""

import pytest
import asyncio


# We don't need to define our own event_loop fixture as pytest-asyncio provides one
# This was causing a deprecation warning