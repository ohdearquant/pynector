"""Error handling utilities for structured concurrency."""

import anyio
from typing import Type, TypeVar, Callable, Awaitable, Any

T = TypeVar('T')


def get_cancelled_exc_class() -> Type[BaseException]:
    """Get the exception class used for cancellation.
    
    Returns:
        The exception class used for cancellation (CancelledError for asyncio,
        Cancelled for trio).
    """
    return anyio.get_cancelled_exc_class()


async def shield(func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
    """Run a coroutine function with protection from cancellation.
    
    Args:
        func: The coroutine function to call
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        The return value of the function
    """
    with anyio.CancelScope(shield=True):
        return await func(*args, **kwargs)