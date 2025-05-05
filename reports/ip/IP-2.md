# Implementation Plan: Structured Concurrency

**Issue:** #2\
**Author:** pynector-implementer\
**Date:** 2025-05-05\
**Status:** Draft

## 1. Introduction

This Implementation Plan (IP) outlines the approach for implementing Structured
Concurrency as specified in [TDS-2.md](../tds/TDS-2.md). The implementation will
leverage AnyIO to provide a consistent interface for structured concurrency
across both asyncio and trio backends, focusing on task groups, cancellation
scopes, and resource management primitives.

## 2. Project Structure

The Structured Concurrency implementation will be organized in the following
directory structure:

```
pynector/
├── concurrency/
│   ├── __init__.py
│   ├── task.py         # Task group implementation
│   ├── cancel.py       # Cancellation scope implementation
│   ├── primitives.py   # Resource management primitives
│   ├── errors.py       # Error handling utilities
│   └── patterns.py     # Common concurrency patterns
└── tests/
    └── concurrency/
        ├── __init__.py
        ├── test_task.py
        ├── test_cancel.py
        ├── test_primitives.py
        ├── test_errors.py
        ├── test_patterns.py
        └── test_integration.py
```

## 3. Implementation Details

### 3.1 Task Groups (`task.py`)

The task group implementation will provide a way to spawn and manage multiple
concurrent tasks while ensuring proper cleanup and error propagation.

```python
from typing import TypeVar, Callable, Any, Awaitable, Optional
from types import TracebackType
import anyio
from anyio import TASK_STATUS_IGNORED

T = TypeVar('T')
R = TypeVar('R')

class TaskGroup:
    """A group of tasks that are treated as a unit."""
    
    def __init__(self):
        """Initialize a new task group."""
        self._task_group = None
    
    async def start_soon(
        self, 
        func: Callable[..., Awaitable[Any]], 
        *args: Any, 
        name: Optional[str] = None
    ) -> None:
        """Start a new task in this task group.
        
        Args:
            func: The coroutine function to call
            *args: Positional arguments to pass to the function
            name: Optional name for the task
            
        Note:
            This method does not wait for the task to initialize.
        """
        if self._task_group is None:
            raise RuntimeError("Task group is not active")
        await self._task_group.start_soon(func, *args, name=name)
        
    async def start(
        self, 
        func: Callable[..., Awaitable[R]], 
        *args: Any, 
        name: Optional[str] = None
    ) -> R:
        """Start a new task and wait for it to initialize.
        
        Args:
            func: The coroutine function to call
            *args: Positional arguments to pass to the function
            name: Optional name for the task
            
        Returns:
            The value passed to task_status.started()
            
        Note:
            The function must accept a task_status keyword argument and call
            task_status.started() once initialization is complete.
        """
        if self._task_group is None:
            raise RuntimeError("Task group is not active")
        return await self._task_group.start(func, *args, name=name)
        
    async def __aenter__(self) -> 'TaskGroup':
        """Enter the task group context.
        
        Returns:
            The task group instance.
        """
        self._task_group = await anyio.create_task_group()
        await self._task_group.__aenter__()
        return self
        
    async def __aexit__(
        self, 
        exc_type: Optional[type[BaseException]], 
        exc_val: Optional[BaseException], 
        exc_tb: Optional[TracebackType]
    ) -> bool:
        """Exit the task group context.
        
        This will wait for all tasks in the group to complete.
        If any task raised an exception, it will be propagated.
        If multiple tasks raised exceptions, they will be combined into an ExceptionGroup.
        
        Returns:
            True if the exception was handled, False otherwise.
        """
        if self._task_group is None:
            return False
        
        result = await self._task_group.__aexit__(exc_type, exc_val, exc_tb)
        self._task_group = None
        return result
```

### 3.2 Factory Function for Task Groups

```python
async def create_task_group() -> TaskGroup:
    """Create a new task group.
    
    Returns:
        A new task group instance.
    
    Example:
        async with create_task_group() as tg:
            await tg.start_soon(task1)
            await tg.start_soon(task2)
    """
    return TaskGroup()
```

### 3.3 Cancellation Scopes (`cancel.py`)

The cancellation scope implementation will provide fine-grained control over
task cancellation and timeouts.

```python
from typing import Optional
from types import TracebackType
import anyio
from contextlib import contextmanager
from typing import TypeVar, Iterator

T = TypeVar('T')

class CancelScope:
    """A context manager for controlling cancellation of tasks."""
    
    def __init__(self, deadline: Optional[float] = None, shield: bool = False):
        """Initialize a new cancel scope.
        
        Args:
            deadline: The time (in seconds since the epoch) when this scope should be cancelled
            shield: If True, this scope shields its contents from external cancellation
        """
        self._scope = None
        self._deadline = deadline
        self._shield = shield
        self.cancel_called = False
        self.cancelled_caught = False
        
    def cancel(self) -> None:
        """Cancel this scope.
        
        This will cause all tasks within this scope to be cancelled.
        """
        if self._scope is None:
            self.cancel_called = True
        else:
            self._scope.cancel()
        
    def __enter__(self) -> 'CancelScope':
        """Enter the cancel scope context.
        
        Returns:
            The cancel scope instance.
        """
        self._scope = anyio.CancelScope(deadline=self._deadline, shield=self._shield)
        if self.cancel_called:
            self._scope.cancel()
        self._scope.__enter__()
        return self
        
    def __exit__(
        self, 
        exc_type: Optional[type[BaseException]], 
        exc_val: Optional[BaseException], 
        exc_tb: Optional[TracebackType]
    ) -> bool:
        """Exit the cancel scope context.
        
        Returns:
            True if the exception was handled, False otherwise.
        """
        if self._scope is None:
            return False
        
        result = self._scope.__exit__(exc_type, exc_val, exc_tb)
        self.cancelled_caught = self._scope.cancelled_caught
        self._scope = None
        return result
```

### 3.4 Timeout Utilities

```python
from contextlib import contextmanager
from typing import Optional, Iterator
import anyio
import time

@contextmanager
def move_on_after(seconds: Optional[float]) -> Iterator[CancelScope]:
    """Return a context manager that cancels its contents after the given number of seconds.
    
    Args:
        seconds: The number of seconds to wait before cancelling, or None to disable the timeout
        
    Returns:
        A cancel scope that will be cancelled after the specified time
        
    Example:
        with move_on_after(5) as scope:
            await long_running_operation()
            if scope.cancelled_caught:
                print("Operation timed out")
    """
    deadline = None if seconds is None else time.time() + seconds
    scope = CancelScope(deadline=deadline)
    with scope:
        yield scope

@contextmanager
def fail_after(seconds: Optional[float]) -> Iterator[CancelScope]:
    """Return a context manager that raises TimeoutError if its contents take longer than the given time.
    
    Args:
        seconds: The number of seconds to wait before raising TimeoutError, or None to disable the timeout
        
    Returns:
        A cancel scope that will raise TimeoutError after the specified time
        
    Raises:
        TimeoutError: If the operation takes longer than the specified time
        
    Example:
        try:
            with fail_after(5):
                await long_running_operation()
        except TimeoutError:
            print("Operation timed out")
    """
    deadline = None if seconds is None else time.time() + seconds
    scope = CancelScope(deadline=deadline)
    with scope:
        yield scope
        if scope.cancelled_caught:
            raise TimeoutError(f"Operation took longer than {seconds} seconds")
```

### 3.5 Resource Management Primitives (`primitives.py`)

The resource management primitives will provide synchronization mechanisms for
coordinating access to shared resources.

#### 3.5.1 Lock

```python
from typing import Optional
from types import TracebackType
import anyio

class Lock:
    """A mutex lock for controlling access to a shared resource.
    
    This lock is reentrant, meaning the same task can acquire it multiple times
    without deadlocking.
    """
    
    def __init__(self):
        """Initialize a new lock."""
        self._lock = anyio.Lock()
    
    async def __aenter__(self) -> None:
        """Acquire the lock.
        
        If the lock is already held by another task, this will wait until it's released.
        """
        await self.acquire()
        
    async def __aexit__(
        self, 
        exc_type: Optional[type[BaseException]], 
        exc_val: Optional[BaseException], 
        exc_tb: Optional[TracebackType]
    ) -> None:
        """Release the lock."""
        self.release()
        
    async def acquire(self) -> bool:
        """Acquire the lock.
        
        Returns:
            True if the lock was acquired, False otherwise.
        """
        await self._lock.acquire()
        return True
        
    def release(self) -> None:
        """Release the lock.
        
        Raises:
            RuntimeError: If the lock is not currently held by this task.
        """
        self._lock.release()
```

#### 3.5.2 Semaphore

```python
from typing import Optional
from types import TracebackType
import anyio

class Semaphore:
    """A semaphore for limiting concurrent access to a resource."""
    
    def __init__(self, initial_value: int):
        """Initialize a new semaphore.
        
        Args:
            initial_value: The initial value of the semaphore (must be >= 0)
        """
        if initial_value < 0:
            raise ValueError("The initial value must be >= 0")
        self._semaphore = anyio.Semaphore(initial_value)
        
    async def __aenter__(self) -> None:
        """Acquire the semaphore.
        
        If the semaphore value is zero, this will wait until it's released.
        """
        await self.acquire()
        
    async def __aexit__(
        self, 
        exc_type: Optional[type[BaseException]], 
        exc_val: Optional[BaseException], 
        exc_tb: Optional[TracebackType]
    ) -> None:
        """Release the semaphore."""
        self.release()
        
    async def acquire(self) -> None:
        """Acquire the semaphore.
        
        If the semaphore value is zero, this will wait until it's released.
        """
        await self._semaphore.acquire()
        
    def release(self) -> None:
        """Release the semaphore, incrementing its value."""
        self._semaphore.release()
```

#### 3.5.3 CapacityLimiter

```python
from typing import Optional
from types import TracebackType
import anyio

class CapacityLimiter:
    """A context manager for limiting the number of concurrent operations."""
    
    def __init__(self, total_tokens: float):
        """Initialize a new capacity limiter.
        
        Args:
            total_tokens: The maximum number of tokens (>= 1)
        """
        if total_tokens < 1:
            raise ValueError("The total number of tokens must be >= 1")
        self._limiter = anyio.CapacityLimiter(total_tokens)
        
    async def __aenter__(self) -> None:
        """Acquire a token.
        
        If no tokens are available, this will wait until one is released.
        """
        await self.acquire()
        
    async def __aexit__(
        self, 
        exc_type: Optional[type[BaseException]], 
        exc_val: Optional[BaseException], 
        exc_tb: Optional[TracebackType]
    ) -> None:
        """Release the token."""
        self.release()
        
    async def acquire(self) -> None:
        """Acquire a token.
        
        If no tokens are available, this will wait until one is released.
        """
        await self._limiter.acquire()
        
    def release(self) -> None:
        """Release a token.
        
        Raises:
            RuntimeError: If the current task doesn't hold any tokens.
        """
        self._limiter.release()
        
    @property
    def total_tokens(self) -> float:
        """The total number of tokens."""
        return self._limiter.total_tokens
        
    @total_tokens.setter
    def total_tokens(self, value: float) -> None:
        """Set the total number of tokens.
        
        Args:
            value: The new total number of tokens (>= 1)
        """
        if value < 1:
            raise ValueError("The total number of tokens must be >= 1")
        self._limiter.total_tokens = value
        
    @property
    def borrowed_tokens(self) -> int:
        """The number of tokens currently borrowed."""
        return self._limiter.borrowed_tokens
        
    @property
    def available_tokens(self) -> float:
        """The number of tokens currently available."""
        return self._limiter.available_tokens
```

#### 3.5.4 Event

```python
import anyio

class Event:
    """An event object for task synchronization.
    
    An event can be in one of two states: set or unset. When set, tasks waiting
    on the event are allowed to proceed.
    """
    
    def __init__(self):
        """Initialize a new event in the unset state."""
        self._event = anyio.Event()
        
    def is_set(self) -> bool:
        """Check if the event is set.
        
        Returns:
            True if the event is set, False otherwise.
        """
        return self._event.is_set()
        
    def set(self) -> None:
        """Set the event, allowing all waiting tasks to proceed."""
        self._event.set()
        
    async def wait(self) -> None:
        """Wait until the event is set."""
        await self._event.wait()
```

#### 3.5.5 Condition

```python
from typing import Optional
from types import TracebackType
import anyio

class Condition:
    """A condition variable for task synchronization."""
    
    def __init__(self, lock: Optional[Lock] = None):
        """Initialize a new condition.
        
        Args:
            lock: The lock to use, or None to create a new one
        """
        self._lock = lock or Lock()
        self._condition = anyio.Condition(self._lock._lock)
        
    async def __aenter__(self) -> 'Condition':
        """Acquire the underlying lock.
        
        Returns:
            The condition instance.
        """
        await self._lock.acquire()
        return self
        
    async def __aexit__(
        self, 
        exc_type: Optional[type[BaseException]], 
        exc_val: Optional[BaseException], 
        exc_tb: Optional[TracebackType]
    ) -> None:
        """Release the underlying lock."""
        self._lock.release()
        
    async def wait(self) -> None:
        """Wait for a notification.
        
        This releases the underlying lock, waits for a notification, and then
        reacquires the lock.
        """
        await self._condition.wait()
        
    async def notify(self, n: int = 1) -> None:
        """Notify waiting tasks.
        
        Args:
            n: The number of tasks to notify
        """
        await self._condition.notify(n)
        
    async def notify_all(self) -> None:
        """Notify all waiting tasks."""
        await self._condition.notify_all()
```

### 3.6 Error Handling Utilities (`errors.py`)

```python
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
```

### 3.7 Concurrency Patterns (`patterns.py`)

The concurrency patterns module will implement common patterns for structured
concurrency.

#### 3.7.1 Connection Pool Pattern

```python
from typing import List, Callable, Awaitable, TypeVar, Optional
from types import TracebackType
import anyio
from pynector.concurrency.primitives import Lock, CapacityLimiter

T = TypeVar('T')

class ConnectionPool:
    """A pool of reusable connections."""
    
    def __init__(self, max_connections: int, connection_factory: Callable[[], Awaitable[T]]):
        """Initialize a new connection pool.
        
        Args:
            max_connections: The maximum number of connections in the pool
            connection_factory: A factory function that creates new connections
        """
        self._connection_factory = connection_factory
        self._limiter = CapacityLimiter(max_connections)
        self._connections: List[T] = []
        self._lock = Lock()
        
    async def acquire(self) -> T:
        """Acquire a connection from the pool.
        
        Returns:
            A connection from the pool, or a new connection if the pool is empty.
        """
        async with self._limiter:
            async with self._lock:
                if self._connections:
                    return self._connections.pop()
            
            # No connections available, create a new one
            return await self._connection_factory()
        
    async def release(self, connection: T) -> None:
        """Release a connection back to the pool.
        
        Args:
            connection: The connection to release
        """
        async with self._lock:
            self._connections.append(connection)
            
    async def __aenter__(self) -> 'ConnectionPool':
        """Enter the connection pool context.
        
        Returns:
            The connection pool instance.
        """
        return self
        
    async def __aexit__(
        self, 
        exc_type: Optional[type[BaseException]], 
        exc_val: Optional[BaseException], 
        exc_tb: Optional[TracebackType]
    ) -> None:
        """Exit the connection pool context, closing all connections."""
        async with self._lock:
            for connection in self._connections:
                if hasattr(connection, 'close'):
                    await connection.close()
                elif hasattr(connection, 'disconnect'):
                    await connection.disconnect()
            self._connections.clear()
```

#### 3.7.2 Parallel Request Pattern

```python
from typing import List, Optional, TypeVar, Any
import anyio
from pynector.concurrency.task import create_task_group
from pynector.concurrency.primitives import CapacityLimiter

T = TypeVar('T')
Response = TypeVar('Response')

async def parallel_requests(
    urls: List[str], 
    fetch_func: Callable[[str], Awaitable[Response]],
    max_concurrency: int = 10
) -> List[Response]:
    """Fetch multiple URLs in parallel with limited concurrency.
    
    Args:
        urls: The URLs to fetch
        fetch_func: The function to use for fetching
        max_concurrency: The maximum number of concurrent requests
        
    Returns:
        A list of responses in the same order as the URLs
    """
    limiter = CapacityLimiter(max_concurrency)
    results: List[Optional[Response]] = [None] * len(urls)
    exceptions: List[Optional[Exception]] = [None] * len(urls)
    
    async def fetch_with_limit(index: int, url: str) -> None:
        async with limiter:
            try:
                results[index] = await fetch_func(url)
            except Exception as exc:
                exceptions[index] = exc
    
    async with create_task_group() as tg:
        for i, url in enumerate(urls):
            await tg.start_soon(fetch_with_limit, i, url)
    
    # Check for exceptions
    for i, exc in enumerate(exceptions):
        if exc is not None:
            raise exc
    
    return results  # type: ignore
```

#### 3.7.3 Timeout Retry Pattern

```python
import anyio
from typing import TypeVar, Callable, Awaitable, Optional, Type
from pynector.concurrency.cancel import move_on_after

T = TypeVar('T')

async def retry_with_timeout(
    func: Callable[..., Awaitable[T]],
    *args: Any,
    max_retries: int = 3,
    timeout: float = 5.0,
    retry_exceptions: Optional[List[Type[Exception]]] = None,
    **kwargs: Any
) -> T:
    """Execute a function with retry logic and timeout.
    
    Args:
        func: The function to call
        *args: Positional arguments to pass to the function
        max_retries: The maximum number of retry attempts
        timeout: The timeout for each attempt in seconds
        retry_exceptions: List of exception types to retry on, or None to retry on any exception
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        The return value of the function
        
    Raises:
        TimeoutError: If all retry attempts time out
        Exception: If the function raises an exception after all retry attempts
    """
    retry_exceptions = retry_exceptions or [Exception]
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            with move_on_after(timeout) as scope:
                result = await func(*args, **kwargs)
                if not scope.cancelled_caught:
                    return result
            
            # If we get here, the operation timed out
            if attempt == max_retries - 1:
                raise TimeoutError(f"Operation timed out after {max_retries} attempts")
            
            # Wait before retrying (exponential backoff)
            await anyio.sleep(2 ** attempt)
            
        except tuple(retry_exceptions) as exc:
            last_exception = exc
            if attempt == max_retries - 1:
                raise
            
            # Wait before retrying (exponential backoff)
            await anyio.sleep(2 ** attempt)
    
    # This should never be reached, but makes the type checker happy
    if last_exception:
        raise last_exception
    raise RuntimeError("Unreachable code")
```

#### 3.7.4 Worker Pool Pattern

```python
from typing import Any, Callable, Awaitable, Optional, List
import anyio
from pynector.concurrency.task import create_task_group, TaskGroup

class WorkerPool:
    """A pool of worker tasks that process items from a queue."""
    
    def __init__(self, num_workers: int, worker_func: Callable[[Any], Awaitable[None]]):
        """Initialize a new worker pool.
        
        Args:
            num_workers: The number of worker tasks to create
            worker_func: The function that each worker will run
        """
        self._num_workers = num_workers
        self._worker_func = worker_func
        self._queue = anyio.Queue()
        self._task_group: Optional[TaskGroup] = None
        
    async def start(self) -> None:
        """Start the worker pool."""
        if self._task_group is not None:
            raise RuntimeError("Worker pool already started")
        
        self._task_group = await create_task_group()
        
        for _ in range(self._num_workers):
            await self._task_group.start_soon(self._worker_loop)
        
    async def stop(self) -> None:
        """Stop the worker pool."""
        if self._task_group is None:
            return
        
        # Signal workers to stop
        for _ in range(self._num_workers):
            await self._queue.put(None)
        
        # Wait for workers to finish
        await self._task_group.__aexit__(None, None, None)
        self._task_group = None
        
    async def submit(self, item: Any) -> None:
        """Submit an item to be processed by a worker.
        
        Args:
            item: The item to process
        """
        if self._task_group is None:
            raise RuntimeError("Worker pool not started")
        
        await self._queue.put(item)
        
    async def _worker_loop(self) -> None:
        """The main loop for each worker task."""
        while True:
            item = await self._queue.get()
            
            # None is a signal to stop
            if item is None:
                break
            
            try:
                await self._worker_func(item)
            except Exception as exc:
                # Log the exception but keep the worker running
                print(f"Worker error: {exc}")
```

## 4. Implementation Approach

The implementation will follow these steps:

1. **Set up project structure:** Create the necessary directories and files
2. **Implement core task group functionality:** Implement the `TaskGroup` class
   and `create_task_group` function
3. **Implement cancellation scopes:** Implement the `CancelScope` class and
   timeout utilities
4. **Implement resource management primitives:** Implement the `Lock`,
   `Semaphore`, `CapacityLimiter`, `Event`, and `Condition` classes
5. **Implement error handling utilities:** Implement the
   `get_cancelled_exc_class` function and other error handling utilities
6. **Implement concurrency patterns:** Implement the `ConnectionPool`, parallel
   request, timeout retry, and worker pool patterns
7. **Write tests:** Write comprehensive tests for all components
8. **Documentation:** Add docstrings and type hints to all components

## 5. Dependencies

The implementation will require the following dependencies:

- Python 3.9 or higher (as specified in pyproject.toml)
- AnyIO 3.7.0 or higher (for structured concurrency primitives)
- Standard library modules:
  - `typing` for type hints
  - `contextlib` for context managers
  - `time` for timeout handling

The implementation will be added to the project's dependencies in
pyproject.toml:

```toml
[tool.poetry.dependencies]
python = "^3.9"
anyio = "^3.7.0"
```

## 6. Testing Strategy

The testing strategy is detailed in the Test Implementation document (TI-2.md).
It will include:

- Unit tests for all components
- Integration tests for component interactions
- Property-based tests for concurrency patterns
- Stress tests for resource management primitives

## 7. References

1. Technical Design Specification: Structured Concurrency (TDS-2.md) (search:
   internal-document)
2. Research Report: Structured Concurrency Patterns in AnyIO (RR-2.md) (search:
   internal-document)
3. AnyIO Documentation (search: exa-anyio.readthedocs.io)
4. AnyIO Tasks Documentation (search:
   exa-anyio.readthedocs.io/en/latest/tasks.html)
5. AnyIO Cancellation Documentation (search:
   exa-anyio.readthedocs.io/en/stable/cancellation.html)
6. AnyIO Synchronization Documentation (search:
   exa-anyio.readthedocs.io/en/stable/synchronization.html)
7. Structured Concurrency in Python with AnyIO (search:
   exa-mattwestcott.org/blog/structured-concurrency-in-python-with-anyio)
8. Stack Overflow - Difference between anyio.TaskGroup and asyncio.TaskGroup
   (search: exa-stackoverflow.com/questions/78060510)
