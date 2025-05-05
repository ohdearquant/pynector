"""Integration tests for the telemetry module."""

import pytest
import asyncio
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
@pytest.mark.parametrize("has_opentelemetry,has_structlog", [
    (True, True),
    (True, False),
    (False, True),
    (False, False)
])
async def test_telemetry_integration(has_opentelemetry, has_structlog):
    """Test that all telemetry components work together correctly."""
    # Mock dependencies availability
    with patch('src.pynector.telemetry.HAS_OPENTELEMETRY', has_opentelemetry), \
         patch('src.pynector.telemetry.facade.HAS_OPENTELEMETRY', has_opentelemetry), \
         patch('src.pynector.telemetry.context.HAS_OPENTELEMETRY', has_opentelemetry), \
         patch('src.pynector.telemetry.config.HAS_OPENTELEMETRY', has_opentelemetry), \
         patch('src.pynector.telemetry.HAS_STRUCTLOG', has_structlog), \
         patch('src.pynector.telemetry.facade.HAS_STRUCTLOG', has_structlog), \
         patch('src.pynector.telemetry.config.HAS_STRUCTLOG', has_structlog):
        
        # Mock configure_telemetry to avoid actual configuration
        with patch('src.pynector.telemetry.config.configure_telemetry', return_value=has_opentelemetry):
            from src.pynector.telemetry import get_telemetry, configure_telemetry
            
            # Configure telemetry
            configure_telemetry(service_name="test-service")
            
            # Get tracer and logger
            tracer, logger = get_telemetry("test-module")
            
            # Test synchronous tracing
            with tracer.start_as_current_span("test-span", {"key": "value"}) as span:
                # Log with structured data
                logger.info("test-event", data="test-data")
                
                # Set span attribute
                span.set_attribute("result", "success")
            
            # Test asynchronous tracing
            async with tracer.start_as_current_async_span("test-async-span") as span:
                # Log with structured data
                logger.info("test-async-event", data="test-async-data")
                
                # Set span attribute
                span.set_attribute("async-result", "success")
                
                # Test error handling
                try:
                    raise ValueError("Test error")
                except ValueError as e:
                    logger.error("test-error", error=str(e))
                    span.record_exception(e)
            
            # Test context propagation
            from src.pynector.telemetry.context import traced_async_operation, traced_gather
            
            async def test_operation():
                return "success"
            
            async with traced_async_operation(tracer, "test-operation") as span:
                result = await test_operation()
                span.set_attribute("operation-result", result)
            
            # Test parallel operations
            async def operation1():
                return "result1"
            
            async def operation2():
                return "result2"
            
            results = await traced_gather(tracer, [operation1(), operation2()], "parallel-operations")
            assert results == ["result1", "result2"]


@pytest.mark.asyncio
async def test_integration_with_real_dependencies():
    """Test with real dependencies if available."""
    try:
        import opentelemetry
        import structlog
        has_dependencies = True
    except ImportError:
        has_dependencies = False
    
    if has_dependencies:
        # Only run this test if dependencies are actually installed
        from src.pynector.telemetry import get_telemetry, configure_telemetry
        
        # Configure telemetry with console exporter
        configure_telemetry(
            service_name="test-service",
            trace_exporters=["console"],
            log_level="DEBUG"
        )
        
        # Get tracer and logger
        tracer, logger = get_telemetry("test-module")
        
        # Test basic functionality
        with tracer.start_as_current_span("test-span") as span:
            logger.info("test-event", data="test-data")
            span.set_attribute("test-attribute", "test-value")
        
        # Test async functionality
        async with tracer.start_as_current_async_span("test-async-span") as span:
            logger.info("test-async-event", data="test-async-data")
            span.set_attribute("test-async-attribute", "test-async-value")
    else:
        # Skip test if dependencies are not available
        pytest.skip("OpenTelemetry and/or structlog not installed")


@pytest.mark.asyncio
async def test_context_propagation_integration():
    """Test context propagation across async boundaries."""
    # Mock dependencies availability
    with patch('src.pynector.telemetry.HAS_OPENTELEMETRY', True), \
         patch('src.pynector.telemetry.facade.HAS_OPENTELEMETRY', True), \
         patch('src.pynector.telemetry.context.HAS_OPENTELEMETRY', True):
        
        # Mock OpenTelemetry context
        mock_context = MagicMock()
        mock_token = MagicMock()
        mock_attach = MagicMock(return_value=mock_token)
        mock_detach = MagicMock()
        mock_get_current = MagicMock(return_value=mock_context)
        
        with patch('src.pynector.telemetry.facade.attach', mock_attach), \
             patch('src.pynector.telemetry.facade.detach', mock_detach), \
             patch('src.pynector.telemetry.facade.get_current', mock_get_current), \
             patch('src.pynector.telemetry.context.attach', mock_attach), \
             patch('src.pynector.telemetry.context.detach', mock_detach), \
             patch('src.pynector.telemetry.context.get_current', mock_get_current):
            
            from src.pynector.telemetry import get_telemetry
            from src.pynector.telemetry.context import traced_gather
            
            # Get tracer
            tracer, _ = get_telemetry("test-module")
            
            # Define test coroutines that use spans
            async def coro1():
                async with tracer.start_as_current_async_span("coro1-span") as span:
                    span.set_attribute("coro", "1")
                    return 1
            
            async def coro2():
                async with tracer.start_as_current_async_span("coro2-span") as span:
                    span.set_attribute("coro", "2")
                    return 2
            
            # Test traced_gather
            results = await traced_gather(tracer, [coro1(), coro2()], "parent-span")
            
            assert results == [1, 2]
            # Verify context was attached and detached
            assert mock_attach.call_count >= 3  # At least once for parent span and once for each coroutine
            assert mock_detach.call_count >= 3  # At least once for parent span and once for each coroutine


@pytest.mark.parametrize("has_opentelemetry,has_structlog", [
    (True, True),
    (True, False),
    (False, True),
    (False, False)
])
def test_error_handling_integration(has_opentelemetry, has_structlog):
    """Test error handling integration."""
    # Mock dependencies availability
    with patch('src.pynector.telemetry.HAS_OPENTELEMETRY', has_opentelemetry), \
         patch('src.pynector.telemetry.facade.HAS_OPENTELEMETRY', has_opentelemetry), \
         patch('src.pynector.telemetry.HAS_STRUCTLOG', has_structlog), \
         patch('src.pynector.telemetry.facade.HAS_STRUCTLOG', has_structlog):
        
        from src.pynector.telemetry import get_telemetry, Status, StatusCode
        
        # Get tracer and logger
        tracer, logger = get_telemetry("test-module")
        
        # Test error handling in synchronous code
        try:
            with tracer.start_as_current_span("error-span") as span:
                logger.error("test-error", error="Test error")
                span.set_status(Status(StatusCode.ERROR))
                raise ValueError("Test error")
        except ValueError:
            pass  # Expected exception
        
        # No assertions needed - if no exceptions are raised during the test, it passes