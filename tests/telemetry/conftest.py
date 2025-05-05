"""
Pytest configuration for telemetry tests.

This module provides fixtures and configuration for testing the telemetry module.
"""

import sys
import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def patch_imports():
    """
    Patch imports to handle the mismatch between src.pynector and pynector.
    
    This fixture is automatically used in all tests in this directory.
    """
    # Create a mapping from src.pynector to pynector
    import pynector
    sys.modules['src.pynector'] = pynector
    
    # Create mappings for telemetry modules
    import pynector.telemetry
    sys.modules['src.pynector.telemetry'] = pynector.telemetry
    
    import pynector.telemetry.facade
    sys.modules['src.pynector.telemetry.facade'] = pynector.telemetry.facade
    
    import pynector.telemetry.tracing
    sys.modules['src.pynector.telemetry.tracing'] = pynector.telemetry.tracing
    
    import pynector.telemetry.logging
    sys.modules['src.pynector.telemetry.logging'] = pynector.telemetry.logging
    
    import pynector.telemetry.context
    sys.modules['src.pynector.telemetry.context'] = pynector.telemetry.context
    
    import pynector.telemetry.config
    sys.modules['src.pynector.telemetry.config'] = pynector.telemetry.config
    
    yield
    
    # Clean up
    for module in list(sys.modules.keys()):
        if module.startswith('src.pynector'):
            del sys.modules[module]