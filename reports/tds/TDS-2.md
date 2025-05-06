# Technical Design Specification: Structured Concurrency

**Issue:** #2\
**Author:** pynector-architect\
**Date:** 2025-05-05\
**Status:** Draft

## 1. Introduction

This Technical Design Specification (TDS) defines the architecture and
implementation details for Structured Concurrency in the pynector project. The
design is based on the research findings documented in [RR-2.md](../rr/RR-2.md)
and additional research.

### 1.1 Purpose

The Structured Concurrency implementation provides a robust, maintainable, and
safe approach to concurrent programming that:

- Enforces proper task lifecycle management and cleanup
- Ensures reliable error propagation between parent and child tasks
- Provides fine-grained control over cancellation and timeouts
- Manages access to shared resources through synchronization primitives
- Works consistently across both asyncio and trio backends via AnyIO

### 1.2 Scope

This specification covers:

- Task group design and implementation
- Cancellation scope patterns
- Resource management primitives (Lock, Semaphore, CapacityLimiter)
- Error propagation strategy
- Timeout handling mechanisms

### 1.3 Design Principles

The design adheres to the following principles:

1. **Task Hierarchy:** Tasks are organized in a parent-child relationship, where
   parent tasks are responsible for their children
2. **Bounded Lifetimes:** Child tasks cannot outlive their parent scope
3. **Error Propagation:** Errors in child tasks propagate to the parent
4. **Automatic Cleanup:** Resources are properly released when tasks complete or
   fail
5. **Cancellation Safety:** Operations that need to complete even during
   cancellation are properly shielded

## 2. Architecture Overview

The Structured Concurrency implementation consists of the following components:

1. **Task Groups:** For managing related concurrent tasks
2. **Cancellation Scopes:** For controlling task cancellation and timeouts
3. **Resource Management Primitives:** For coordinating access to shared
   resources
4. **Error Handling:** For propagating and handling exceptions in concurrent
   code

### 2.1 Component Diagram

```
┌─────────────────────────────────────┐
│           Client Application        │
└───────────────┬─────────────────────┘
                │
                ▼
┌─────────────────────────────────────┐
│           Task Groups               │
├─────────────────────────────────────┤
│  - create_task_group()              │
│  - start_soon()                     │
│  - start()                          │
└───────────────┬─────────────────────┘
                │ uses
                ▼
┌─────────────────────────────────────┐
│        Cancellation Scopes          │
├─────────────────────────────────────┤
│  - CancelScope                      │
│  - move_on_after()                  │
│  - fail_after()                     │
└───────────────┬─────────────────────┘
                │ uses
                ▼
┌─────────────────────────────────────┐
│    Resource Management Primitives   │
├─────────────────────────────────────┤
│  - Lock                             │
│  - Semaphore                        │
│  - CapacityLimiter                  │
│  - Event                            │
│  - Condition                        │
└─────────────────────────────────────┘
```

## 3. Task Groups

Task groups are the fundamental building block of structured concurrency,
providing a way to spawn and manage multiple concurrent tasks while ensuring
proper cleanup and error propagation.

### 3.1 Interface Definition

```python
from typing import TypeVar, Callable, Any, Awaitable, Optional
from types import TracebackType
from anyio import TASK_STATUS_IGNORED

T = TypeVar('T')
R = TypeVar('R')

class TaskGroup:
    """A group of tasks that are treated as a unit."""

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
        ...

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
        ...

    async def __aenter__(self) -> 'TaskGroup':
        """Enter the task group context.

        Returns:
            The task group instance.
        """
        ...

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
        ...
```

### 3.2 Factory Function

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
    ...
```

### 3.3 Task Initialization Pattern

```python
from anyio import TaskStatus

async def server_task(task_status: TaskStatus[int] = TASK_STATUS_IGNORED) -> None:
    """Example task that signals when initialization is complete.

    Args:
        task_status: Object used to signal task initialization.
    """
    # Perform initialization
    server = await start_server()
    port = server.port

    # Signal that initialization is complete
    await task_status.started(port)

    # Run the main task logic
    await server.serve()
```

### 3.4 Usage Example

```python
async def main():
    """Example usage of task groups."""
    async with create_task_group() as tg:
        # Start tasks without waiting for initialization
        await tg.start_soon(background_task)
        await tg.start_soon(another_task)

        # Start a task and wait for initialization
        port = await tg.start(server_task)
        print(f"Server started on port {port}")

    # All tasks are guaranteed to be complete here
```

## 4. Cancellation and Timeouts

Cancellation scopes provide fine-grained control over task cancellation and
timeouts, allowing for graceful handling of long-running operations.

### 4.1 CancelScope Interface

```python
from typing import Optional
from types import TracebackType

class CancelScope:
    """A context manager for controlling cancellation of tasks."""

    def __init__(self, deadline: Optional[float] = None, shield: bool = False):
        """Initialize a new cancel scope.

        Args:
            deadline: The time (in seconds since the epoch) when this scope should be cancelled
            shield: If True, this scope shields its contents from external cancellation
        """
        self.deadline = deadline
        self.shield = shield
        self.cancel_called = False
        self.cancelled_caught = False

    def cancel(self) -> None:
        """Cancel this scope.

        This will cause all tasks within this scope to be cancelled.
        """
        self.cancel_called = True

    def __enter__(self) -> 'CancelScope':
        """Enter the cancel scope context.

        Returns:
            The cancel scope instance.
        """
        ...

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
        ...
```

### 4.2 Timeout Utilities

```python
from contextlib import contextmanager
from typing import TypeVar, Optional, Iterator

T = TypeVar('T')

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
    ...

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
    ...
```

### 4.3 Cancellation Handling

```python
from anyio import get_cancelled_exc_class

async def task_with_cleanup():
    """Example task that handles cancellation gracefully."""
    try:
        await long_running_operation()
    except get_cancelled_exc_class():
        # Perform cleanup that must not be interrupted
        with CancelScope(shield=True):
            await cleanup_resources()
        # Re-raise the cancellation exception
        raise
```

### 4.4 Usage Examples

```python
async def timeout_examples():
    """Examples of timeout handling."""
    # Example with move_on_after
    with move_on_after(5) as scope:
        await long_running_operation()
        if scope.cancelled_caught:
            print("Operation timed out, using fallback")
            return fallback_result()

    # Example with fail_after
    try:
        with fail_after(5):
            await long_running_operation()
    except TimeoutError:
        print("Operation timed out")
        raise
```

## 5. Resource Management Primitives

Resource management primitives provide synchronization mechanisms for
coordinating access to shared resources in concurrent code.

### 5.1 Lock

```python
class Lock:
    """A mutex lock for controlling access to a shared resource.

    This lock is reentrant, meaning the same task can acquire it multiple times
    without deadlocking.
    """

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
        ...

    def release(self) -> None:
        """Release the lock.

        Raises:
            RuntimeError: If the lock is not currently held by this task.
        """
        ...
```

### 5.2 Semaphore

```python
class Semaphore:
    """A semaphore for limiting concurrent access to a resource."""

    def __init__(self, initial_value: int):
        """Initialize a new semaphore.

        Args:
            initial_value: The initial value of the semaphore (must be >= 0)
        """
        if initial_value < 0:
            raise ValueError("The initial value must be >= 0")
        self._value = initial_value

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
        ...

    def release(self) -> None:
        """Release the semaphore, incrementing its value."""
        ...
```

### 5.3 CapacityLimiter

```python
class CapacityLimiter:
    """A context manager for limiting the number of concurrent operations."""

    def __init__(self, total_tokens: float):
        """Initialize a new capacity limiter.

        Args:
            total_tokens: The maximum number of tokens (>= 1)
        """
        if total_tokens < 1:
            raise ValueError("The total number of tokens must be >= 1")
        self._total_tokens = total_tokens
        self._borrowed_tokens = 0

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
        ...

    def release(self) -> None:
        """Release a token.

        Raises:
            RuntimeError: If the current task doesn't hold any tokens.
        """
        ...

    @property
    def total_tokens(self) -> float:
        """The total number of tokens."""
        return self._total_tokens

    @total_tokens.setter
    def total_tokens(self, value: float) -> None:
        """Set the total number of tokens.

        Args:
            value: The new total number of tokens (>= 1)
        """
        if value < 1:
            raise ValueError("The total number of tokens must be >= 1")
        self._total_tokens = value

    @property
    def borrowed_tokens(self) -> int:
        """The number of tokens currently borrowed."""
        return self._borrowed_tokens

    @property
    def available_tokens(self) -> float:
        """The number of tokens currently available."""
        return self._total_tokens - self._borrowed_tokens
```

### 5.4 Event

```python
class Event:
    """An event object for task synchronization.

    An event can be in one of two states: set or unset. When set, tasks waiting
    on the event are allowed to proceed. Once set, an event cannot be unset.
    """

    def __init__(self):
        """Initialize a new event in the unset state."""
        self._set = False

    def is_set(self) -> bool:
        """Check if the event is set.

        Returns:
            True if the event is set, False otherwise.
        """
        return self._set

    def set(self) -> None:
        """Set the event, allowing all waiting tasks to proceed."""
        self._set = True

    async def wait(self) -> None:
        """Wait until the event is set."""
        if not self._set:
            # Wait for the event to be set
            ...
```

### 5.5 Condition

```python
class Condition:
    """A condition variable for task synchronization."""

    def __init__(self, lock: Optional[Lock] = None):
        """Initialize a new condition.

        Args:
            lock: The lock to use, or None to create a new one
        """
        self._lock = lock or Lock()

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
        ...

    async def notify(self, n: int = 1) -> None:
        """Notify waiting tasks.

        Args:
            n: The number of tasks to notify
        """
        ...

    async def notify_all(self) -> None:
        """Notify all waiting tasks."""
        ...
```

### 5.6 Usage Examples

```python
async def lock_example():
    """Example usage of Lock."""
    lock = Lock()

    async def access_shared_resource():
        async with lock:
            # Access the shared resource safely
            ...

    async with create_task_group() as tg:
        for _ in range(10):
            await tg.start_soon(access_shared_resource)

async def capacity_limiter_example():
    """Example usage of CapacityLimiter."""
    limiter = CapacityLimiter(10)  # Limit to 10 concurrent operations

    async def limited_operation(url):
        async with limiter:
            # Perform the operation (only 10 can run concurrently)
            return await fetch(url)

    async with create_task_group() as tg:
        for url in urls:
            await tg.start_soon(limited_operation, url)
```

## 6. Error Handling

Proper error handling is crucial in concurrent code to ensure that failures are
properly detected and handled.

### 6.1 Exception Propagation

In structured concurrency, exceptions from child tasks propagate to the parent
task group:

```python
async def exception_propagation_example():
    """Example of exception propagation in task groups."""
    try:
        async with create_task_group() as tg:
            await tg.start_soon(task_that_might_fail)
            await tg.start_soon(another_task)
    except Exception as exc:
        # Handle the exception
        print(f"Task failed: {exc}")
```

### 6.2 ExceptionGroup Handling

When multiple tasks raise exceptions, they are collected into an
`ExceptionGroup`:

```python
async def exception_group_example():
    """Example of handling multiple exceptions from task groups."""
    try:
        async with create_task_group() as tg:
            await tg.start_soon(task_that_might_fail)
            await tg.start_soon(another_task_that_might_fail)
    except* Exception as eg:
        # Handle the exception group
        for exc in eg.exceptions:
            print(f"Task failed: {exc}")
```

### 6.3 Cancellation Exception Handling

To handle cancellation exceptions regardless of the backend, use
`get_cancelled_exc_class()`:

```python
from anyio import get_cancelled_exc_class

async def cancellation_handling_example():
    """Example of handling cancellation exceptions."""
    try:
        await long_running_operation()
    except get_cancelled_exc_class():
        # Perform cleanup that must not be interrupted
        with CancelScope(shield=True):
            await cleanup_resources()
        # Re-raise the cancellation exception
        raise
```

### 6.4 Error Handling Strategy

1. **Categorization:** Errors are categorized into task errors, cancellation
   errors, and timeout errors.
2. **Propagation:** Errors propagate from child tasks to parent task groups.
3. **Grouping:** Multiple errors are collected into `ExceptionGroup` instances.
4. **Cleanup:** Resources are properly cleaned up even when errors occur.

## 7. Implementation Patterns

This section provides concrete implementation patterns for common concurrency
scenarios in pynector.

### 7.1 Connection Pool Pattern

```python
class ConnectionPool:
    """A pool of reusable connections."""

    def __init__(self, max_connections: int, connection_factory: Callable[[], Awaitable[Connection]]):
        """Initialize a new connection pool.

        Args:
            max_connections: The maximum number of connections in the pool
            connection_factory: A factory function that creates new connections
        """
        self._connection_factory = connection_factory
        self._limiter = CapacityLimiter(max_connections)
        self._connections: List[Connection] = []
        self._lock = Lock()

    async def acquire(self) -> Connection:
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

    async def release(self, connection: Connection) -> None:
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
                await connection.close()
            self._connections.clear()
```

### 7.2 Parallel Request Pattern

```python
async def parallel_requests(urls: List[str], max_concurrency: int = 10) -> List[Response]:
    """Fetch multiple URLs in parallel with limited concurrency.

    Args:
        urls: The URLs to fetch
        max_concurrency: The maximum number of concurrent requests

    Returns:
        A list of responses in the same order as the URLs
    """
    limiter = CapacityLimiter(max_concurrency)
    results: List[Optional[Response]] = [None] * len(urls)

    async def fetch_with_limit(index: int, url: str) -> None:
        async with limiter:
            try:
                results[index] = await fetch(url)
            except Exception as exc:
                results[index] = exc

    async with create_task_group() as tg:
        for i, url in enumerate(urls):
            await tg.start_soon(fetch_with_limit, i, url)

    # Check for exceptions
    for result in results:
        if isinstance(result, Exception):
            raise result

    return results  # type: ignore
```

### 7.3 Timeout Retry Pattern

```python
async def fetch_with_retry(url: str, max_retries: int = 3, timeout: float = 5.0) -> Response:
    """Fetch a URL with retry logic and timeout.

    Args:
        url: The URL to fetch
        max_retries: The maximum number of retry attempts
        timeout: The timeout for each attempt in seconds

    Returns:
        The response from the server

    Raises:
        TimeoutError: If all retry attempts time out
        ConnectionError: If the connection fails after all retry attempts
    """
    for attempt in range(max_retries):
        try:
            with move_on_after(timeout) as scope:
                response = await fetch(url)
                if not scope.cancelled_caught:
                    return response

            # If we get here, the operation timed out
            if attempt == max_retries - 1:
                raise TimeoutError(f"Failed to fetch {url} after {max_retries} attempts")

            # Wait before retrying (exponential backoff)
            await anyio.sleep(2 ** attempt)

        except ConnectionError:
            if attempt == max_retries - 1:
                raise

            # Wait before retrying (exponential backoff)
            await anyio.sleep(2 ** attempt)

    # This should never be reached, but makes the type checker happy
    raise RuntimeError("Unreachable code")
```

### 7.4 Worker Pool Pattern

```python
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
        self._queue: Queue[Any] = Queue()
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

## 8. Implementation Considerations

### 8.1 Backend Compatibility

To ensure compatibility with both asyncio and trio backends:

1. **Use AnyIO:** All concurrency primitives should be imported from AnyIO, not
   directly from asyncio or trio.
2. **Backend-agnostic code:** Avoid using backend-specific features or APIs.
3. **Cancellation handling:** Use `get_cancelled_exc_class()` to handle
   cancellation exceptions.

### 8.2 Resource Management

To ensure proper resource management:

1. **Context managers:** Use async context managers for resource acquisition and
   release.
2. **Cleanup in finally blocks:** Ensure resources are cleaned up in finally
   blocks.
3. **Shielded cleanup:** Use shielded cancel scopes for cleanup operations that
   use `await`.

### 8.3 Error Handling

To ensure proper error handling:

1. **Exception propagation:** Let exceptions propagate to the appropriate level.
2. **ExceptionGroup handling:** Be prepared to handle multiple exceptions from
   task groups.
3. **Cancellation handling:** Always re-raise cancellation exceptions after
   cleanup.

### 8.4 Performance Considerations

To ensure good performance:

1. **Limit concurrency:** Use CapacityLimiter to prevent resource exhaustion.
2. **Avoid blocking:** Ensure all operations are truly asynchronous.
3. **Timeouts:** Use timeouts to prevent operations from hanging indefinitely.

## 9. Future Considerations

The following areas are identified for future expansion:

1. **Structured concurrency with threads:** Support for structured concurrency
   with threads via AnyIO's thread support.
2. **Distributed task groups:** Support for task groups that span multiple
   processes or machines.
3. **Monitoring and observability:** Support for monitoring and observing
   concurrent tasks.
4. **Backpressure mechanisms:** More sophisticated backpressure mechanisms for
   handling overload.
5. **Integration with other concurrency libraries:** Support for integration
   with other concurrency libraries like asyncstdlib.

## 10. References

1. Research Report: Structured Concurrency Patterns in AnyIO (RR-2.md) (search:
   internal-document)
2. AnyIO Documentation (search: exa-anyio.readthedocs.io)
3. AnyIO Tasks Documentation (search:
   exa-anyio.readthedocs.io/en/latest/tasks.html)
4. AnyIO Cancellation Documentation (search:
   exa-anyio.readthedocs.io/en/stable/cancellation.html)
5. AnyIO Synchronization Documentation (search:
   exa-anyio.readthedocs.io/en/stable/synchronization.html)
6. Structured Concurrency in Python with AnyIO (search:
   exa-mattwestcott.org/blog/structured-concurrency-in-python-with-anyio)
7. Stack Overflow - Difference between anyio.TaskGroup and asyncio.TaskGroup
   (search: exa-stackoverflow.com/questions/78060510)
8. Mastering Exception Handling in Asynchronous Python (search:
   exa-mysteryweevil.medium.com/mastering-exception-handling-in-asynchronous-python-a-practical-guide-75d9ae18939a)
9. Asyncio Timeout Best Practices (search:
   exa-superfastpython.com/asyncio-timeout-best-practices)
10. AnyIO: All You Need for Async Programming (search:
    exa-lewoudar.medium.com/anyio-all-you-need-for-async-programming-stuff-4cd084d0f6bd)
11. Notes on structured concurrency, or: Go statement considered harmful
    (search:
    exa-vorpus.org/blog/notes-on-structured-concurrency-or-go-statement-considered-harmful)
12. Trio: Structured Concurrency for Python (search:
    exa-trio.readthedocs.io/en/stable/reference-core.html)
