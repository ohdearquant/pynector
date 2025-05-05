"""Tests for the context propagation utilities."""

import pytest
import asyncio
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
async def test_traced_async_operation():
    """Test traced_async_operation context manager."""
    # Create a mock tracer
    mock_span = MagicMock()
    mock_tracer = MagicMock()
    mock_tracer.start_as_current_async_span = MagicMock()
    mock_tracer.start_as_current_async_span.return_value.__aenter__ = MagicMock(return_value=mock_span)
    mock_tracer.start_as_current_async_span.return_value.__aexit__ = MagicMock(return_value=None)
    
    from src.pynector.telemetry.context import traced_async_operation
    
    # Test successful operation
    async with traced_async_operation(mock_tracer, "test_operation", {"key": "value"}) as span:
        assert span == mock_span
        # Perform some operation
        result = 42
    
    mock_tracer.start_as_current_async_span.assert_called_once_with("test_operation", attributes={"key": "value"})
    
    # Test operation with exception
    with pytest.raises(ValueError):
        async with traced_async_operation(mock_tracer, "test_operation") as span:
            assert span == mock_span
            raise ValueError("Test exception")
    
    # Verify exception was recorded and status set to error
    mock_span.record_exception.assert_called_once()
    mock_span.set_status.assert_called_once()
    from src.pynector.telemetry import StatusCode
    assert mock_span.set_status.call_args[0][0].status_code == StatusCode.ERROR


@pytest.mark.asyncio
@pytest.mark.parametrize("has_opentelemetry", [True, False])
async def test_traced_gather(has_opentelemetry):
    """Test traced_gather function."""
    # Mock OpenTelemetry availability
    with patch('src.pynector.telemetry.context.HAS_OPENTELEMETRY', has_opentelemetry):
        if has_opentelemetry:
            # Mock the context module
            mock_token = MagicMock()
            mock_context = MagicMock()
            mock_attach = MagicMock(return_value=mock_token)
            mock_detach = MagicMock()
            mock_get_current = MagicMock(return_value=mock_context)
            
            # Create a mock tracer
            mock_span = MagicMock()
            mock_tracer = MagicMock()
            mock_tracer.start_as_current_async_span = MagicMock()
            mock_tracer.start_as_current_async_span.return_value.__aenter__ = MagicMock(return_value=mock_span)
            mock_tracer.start_as_current_async_span.return_value.__aexit__ = MagicMock(return_value=None)
            
            with patch('src.pynector.telemetry.context.attach', mock_attach), \
                 patch('src.pynector.telemetry.context.detach', mock_detach), \
                 patch('src.pynector.telemetry.context.get_current', mock_get_current):
                
                from src.pynector.telemetry.context import traced_gather
                
                # Create test coroutines
                async def coro1():
                    return 1
                
                async def coro2():
                    return 2
                
                # Test traced_gather
                results = await traced_gather(mock_tracer, [coro1(), coro2()], "test_gather")
                
                assert results == [1, 2]
                mock_tracer.start_as_current_async_span.assert_called_once_with("test_gather")
                assert mock_attach.call_count == 2
                assert mock_detach.call_count == 2
        else:
            # Create test coroutines
            async def coro1():
                return 1
            
            async def coro2():
                return 2
            
            from src.pynector.telemetry.context import traced_gather
            
            # Test traced_gather without OpenTelemetry
            results = await traced_gather(MagicMock(), [coro1(), coro2()], "test_gather")
            
            assert results == [1, 2]


@pytest.mark.asyncio
@pytest.mark.parametrize("has_opentelemetry", [True, False])
async def test_traced_task_group(has_opentelemetry):
    """Test traced_task_group function."""
    # Mock OpenTelemetry availability
    with patch('src.pynector.telemetry.context.HAS_OPENTELEMETRY', has_opentelemetry):
        if has_opentelemetry:
            # Mock the context module
            mock_token = MagicMock()
            mock_context = MagicMock()
            mock_attach = MagicMock(return_value=mock_token)
            mock_detach = MagicMock()
            mock_get_current = MagicMock(return_value=mock_context)
            
            # Create a mock tracer
            mock_span = MagicMock()
            mock_tracer = MagicMock()
            mock_tracer.start_as_current_async_span = MagicMock()
            mock_tracer.start_as_current_async_span.return_value.__aenter__ = MagicMock(return_value=mock_span)
            mock_tracer.start_as_current_async_span.return_value.__aexit__ = MagicMock(return_value=None)
            
            # Mock anyio task group
            mock_task_group = MagicMock()
            mock_create_task_group = MagicMock(return_value=mock_task_group)
            
            with patch('src.pynector.telemetry.context.attach', mock_attach), \
                 patch('src.pynector.telemetry.context.detach', mock_detach), \
                 patch('src.pynector.telemetry.context.get_current', mock_get_current), \
                 patch('src.pynector.telemetry.context.create_task_group', mock_create_task_group):
                
                from src.pynector.telemetry.context import traced_task_group
                
                # Test traced_task_group
                task_group = await traced_task_group(mock_tracer, "test_task_group", {"key": "value"})
                
                assert task_group == mock_task_group
                mock_tracer.start_as_current_async_span.assert_called_once_with("test_task_group", attributes={"key": "value"})
                mock_create_task_group.assert_called_once()
                
                # Test that start_soon was wrapped
                assert task_group.start_soon != mock_task_group.start_soon
                
                # Test wrapped start_soon
                async def test_func():
                    return 42
                
                await task_group.start_soon(test_func)
                mock_task_group.start_soon.assert_called_once()
        else:
            # Mock anyio task group
            mock_task_group = MagicMock()
            mock_create_task_group = MagicMock(return_value=mock_task_group)
            
            with patch('src.pynector.telemetry.context.create_task_group', mock_create_task_group):
                from src.pynector.telemetry.context import traced_task_group
                
                # Test traced_task_group without OpenTelemetry
                task_group = await traced_task_group(MagicMock(), "test_task_group", {"key": "value"})
                
                assert task_group == mock_task_group
                mock_create_task_group.assert_called_once()