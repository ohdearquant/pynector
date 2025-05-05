# Test Implementation: Structured Concurrency

**Issue:** #2\
**Author:** pynector-implementer\
**Date:** 2025-05-05\
**Status:** Draft

## 1. Introduction

This Test Implementation (TI) document outlines the testing strategy for the
Structured Concurrency implementation as specified in
[TDS-2.md](../tds/TDS-2.md) and implemented according to
[IP-2.md](../ip/IP-2.md). The testing approach follows Test-Driven Development
(TDD) principles and aims to achieve >80% code coverage.

## 2. Test Structure

The tests will be organized in the following directory structure:

```
tests/
└── concurrency/
    ├── __init__.py
    ├── test_task.py         # Tests for TaskGroup
    ├── test_cancel.py       # Tests for CancelScope and timeout utilities
    ├── test_primitives.py   # Tests for resource management primitives
    ├── test_errors.py       # Tests for error handling utilities
    ├── test_patterns.py     # Tests for concurrency patterns
    └── test_integration.py  # Integration tests for all components
```

## 3. Testing Framework and Tools

The tests will use the following tools:

- **pytest**: Primary testing framework
- **pytest-asyncio**: For testing async code
- **pytest-cov**: For measuring code coverage
- **hypothesis**: For property-based testing
- **anyio.to_thread.run_sync**: For testing thread safety

## 4. Test Cases

### 4.1 Task Group Tests (`test_task.py`)

These tests will verify that the TaskGroup implementation correctly manages task
lifecycles and error propagation.

#### 4.1.1 Basic Task Group Tests

````python
import pytest
import anyio
from pynector.concurrency.task import TaskGroup, create_task_group

@pytest.mark.asyncio
async def test_task_group_creation():
    """Test that task groups can be created."""
    async with create_task_group() as tg:
        assert isinstance(tg, TaskGroup)

@pytest.mark.asyncio
async def test_task_group_start_soon():
    """Test that tasks can be started with start_soon."""
    results = []
    
    async def task(value):
        results.append(value)
    
    async with create_task_group() as tg:
        await tg.start_soon(task, 1)
        await tg.start_soon(task, 2)
        await tg.start_soon(task, 3)
    
    # After the task group exits, all tasks should be complete
    assert sorted(results) == [1, 2, 3]
@pytest.mark.asyncio
async def test_task_group_start():
    """Test that tasks can be started with start and return values."""
    async def server_task(task_status=anyio.TASK_STATUS_IGNORED):
        await task_status.started(42)
        await anyio.sleep(0.1)
        return "done"
    
    async with create_task_group() as tg:
        port = await tg.start(server_task)
        assert port == 42

@pytest.mark.asyncio
async def test_task_group_outside_context():
    """Test that using a task group outside its context raises an error."""
    tg = await create_task_group()
    
    async def task():
        pass
    
    with pytest.raises(RuntimeError):
        await tg.start_soon(task)
    
    with pytest.raises(RuntimeError):
        await tg.start(task)

#### 4.1.2 Task Group Error Propagation Tests

```python
@pytest.mark.asyncio
async def test_task_group_error_propagation():
    """Test that errors in child tasks propagate to the parent."""
    async def failing_task():
        raise ValueError("Task failed")
    
    with pytest.raises(ValueError, match="Task failed"):
        async with create_task_group() as tg:
            await tg.start_soon(failing_task)

@pytest.mark.asyncio
async def test_task_group_multiple_errors():
    """Test that multiple errors are collected into an ExceptionGroup."""
    async def failing_task_1():
        raise ValueError("Task 1 failed")
    
    async def failing_task_2():
        raise RuntimeError("Task 2 failed")
    
    try:
        async with create_task_group() as tg:
            await tg.start_soon(failing_task_1)
            await tg.start_soon(failing_task_2)
    except* Exception as eg:
        # Check that both exceptions are in the group
        assert len(eg.exceptions) == 2
        assert any(isinstance(e, ValueError) for e in eg.exceptions)
        assert any(isinstance(e, RuntimeError) for e in eg.exceptions)
    else:
        pytest.fail("Expected ExceptionGroup was not raised")
````

### 4.2 Cancellation Scope Tests (`test_cancel.py`)

These tests will verify that the CancelScope implementation correctly handles
cancellation and timeouts.

#### 4.2.1 Basic Cancellation Tests

````python
import pytest
import anyio
import time
from pynector.concurrency.cancel import CancelScope, move_on_after, fail_after

@pytest.mark.asyncio
async def test_cancel_scope_creation():
    """Test that cancel scopes can be created."""
    with CancelScope() as scope:
        assert not scope.cancelled_caught
        assert not scope.cancel_called

@pytest.mark.asyncio
async def test_cancel_scope_cancellation():
    """Test that cancel scopes can be cancelled."""
    with CancelScope() as scope:
        scope.cancel()
        assert scope.cancel_called
        # The scope is cancelled, but we're still in the with block
        # so cancelled_caught is not set yet
        assert not scope.cancelled_caught
    
    # After exiting the with block, cancelled_caught should be set
    assert scope.cancelled_caught
@pytest.mark.asyncio
async def test_cancel_scope_deadline():
    """Test that cancel scopes respect deadlines."""
    deadline = time.time() + 0.1
    with CancelScope(deadline=deadline) as scope:
        await anyio.sleep(0.2)
        # The scope should be cancelled by now
        assert scope.cancelled_caught

#### 4.2.2 Timeout Utility Tests

```python
@pytest.mark.asyncio
async def test_move_on_after():
    """Test that move_on_after cancels operations after the timeout."""
    results = []
    
    async def slow_operation():
        try:
            await anyio.sleep(0.5)
            results.append("completed")
        except anyio.get_cancelled_exc_class():
            results.append("cancelled")
            raise
    
    with move_on_after(0.1) as scope:
        try:
            await slow_operation()
        except anyio.get_cancelled_exc_class():
            results.append("caught")
    
    assert scope.cancelled_caught
    assert "cancelled" in results
    assert "caught" not in results  # The exception should be caught by move_on_after
    assert "completed" not in results

@pytest.mark.asyncio
async def test_fail_after():
    """Test that fail_after raises TimeoutError after the timeout."""
    async def slow_operation():
        await anyio.sleep(0.5)
        return "completed"
    
    with pytest.raises(TimeoutError):
        with fail_after(0.1):
            await slow_operation()
````

#### 4.2.3 Cancellation Handling Tests

```python
@pytest.mark.asyncio
async def test_shield():
    """Test that shielded operations are protected from cancellation."""
    from pynector.concurrency.errors import shield
    
    results = []
    
    async def cleanup():
        await anyio.sleep(0.1)
        results.append("cleanup_completed")
        return "cleanup_result"
    
    async def task_with_cleanup():
        try:
            await anyio.sleep(0.5)
            results.append("task_completed")
        except anyio.get_cancelled_exc_class():
            results.append("task_cancelled")
            cleanup_result = await shield(cleanup)
            assert cleanup_result == "cleanup_result"
            raise
    
    with move_on_after(0.2) as scope:
        try:
            await task_with_cleanup()
        except anyio.get_cancelled_exc_class():
            results.append("caught")
    
    assert "task_cancelled" in results
    assert "cleanup_completed" in results
    assert "task_completed" not in results
```

### 4.3 Resource Management Primitive Tests (`test_primitives.py`)

These tests will verify that the resource management primitives correctly
coordinate access to shared resources.

#### 4.3.1 Lock Tests

```python
import pytest
import anyio
from pynector.concurrency.primitives import Lock
from pynector.concurrency.task import create_task_group

@pytest.mark.asyncio
async def test_lock_basic():
    """Test basic lock functionality."""
    lock = Lock()
    
    # Test that the lock can be acquired and released
    await lock.acquire()
    assert lock._lock._owner is not None
    lock.release()
    assert lock._lock._owner is None
    
    # Test async context manager
    async with lock:
        assert lock._lock._owner is not None
    assert lock._lock._owner is None

@pytest.mark.asyncio
async def test_lock_contention():
    """Test that locks properly handle contention."""
    lock = Lock()
    counter = 0
    results = []
    
    async def increment(task_id, delay):
        nonlocal counter
        await anyio.sleep(delay)
        async with lock:
            # Simulate a non-atomic operation
            current = counter
            await anyio.sleep(0.01)
            counter = current + 1
            results.append(task_id)
    
    async with create_task_group() as tg:
        # Start tasks in reverse order to ensure they don't naturally execute in order
        await tg.start_soon(increment, 3, 0.03)
        await tg.start_soon(increment, 2, 0.02)
        await tg.start_soon(increment, 1, 0.01)
    
    # Counter should be incremented exactly once per task
    assert counter == 3
    # Results should be in the order the tasks acquired the lock
    assert len(results) == 3
```

#### 4.3.2 Semaphore Tests

```python
import pytest
import anyio
from pynector.concurrency.primitives import Semaphore
from pynector.concurrency.task import create_task_group

@pytest.mark.asyncio
async def test_semaphore_basic():
    """Test basic semaphore functionality."""
    sem = Semaphore(2)
    
    # Test that the semaphore can be acquired and released
    await sem.acquire()
    await sem.acquire()
    # The semaphore is now at 0
    sem.release()
    sem.release()
    
    # Test async context manager
    async with sem:
        # The semaphore is now at 1
        async with sem:
            # The semaphore is now at 0
            pass
        # The semaphore is now at 1
@pytest.mark.asyncio
async def test_semaphore_contention():
    """Test that semaphores properly handle contention."""
    sem = Semaphore(2)
    active = 0
    max_active = 0
    results = []
    
    async def task(task_id):
        nonlocal active, max_active
        async with sem:
            active += 1
            max_active = max(max_active, active)
            results.append(f"start-{task_id}")
            await anyio.sleep(0.1)
            results.append(f"end-{task_id}")
            active -= 1
    
    async with create_task_group() as tg:
        for i in range(5):
            await tg.start_soon(task, i)
    
    # At most 2 tasks should have been active at once
    assert max_active == 2
    # All tasks should have completed
    assert len(results) == 10
```

#### 4.3.3 CapacityLimiter Tests

```python
import pytest
import anyio
from pynector.concurrency.primitives import CapacityLimiter
from pynector.concurrency.task import create_task_group

@pytest.mark.asyncio
async def test_capacity_limiter_basic():
    """Test basic capacity limiter functionality."""
    limiter = CapacityLimiter(2)
    
    # Test properties
    assert limiter.total_tokens == 2
    assert limiter.borrowed_tokens == 0
    assert limiter.available_tokens == 2
    
    # Test that the limiter can be acquired and released
    await limiter.acquire()
    assert limiter.borrowed_tokens == 1
    assert limiter.available_tokens == 1
    
    await limiter.acquire()
    assert limiter.borrowed_tokens == 2
    assert limiter.available_tokens == 0
    
    limiter.release()
    assert limiter.borrowed_tokens == 1
    assert limiter.available_tokens == 1
    
    limiter.release()
    assert limiter.borrowed_tokens == 0
    assert limiter.available_tokens == 2
    
    # Test async context manager
    async with limiter:
        assert limiter.borrowed_tokens == 1
    assert limiter.borrowed_tokens == 0

@pytest.mark.asyncio
async def test_capacity_limiter_contention():
    """Test that capacity limiters properly handle contention."""
    limiter = CapacityLimiter(2)
    active = 0
    max_active = 0
    results = []
    
    async def task(task_id):
        nonlocal active, max_active
        async with limiter:
            active += 1
            max_active = max(max_active, active)
            results.append(f"start-{task_id}")
            await anyio.sleep(0.1)
            results.append(f"end-{task_id}")
            active -= 1
    
    async with create_task_group() as tg:
        for i in range(5):
            await tg.start_soon(task, i)
    
    # At most 2 tasks should have been active at once
    assert max_active == 2
    # All tasks should have completed
    assert len(results) == 10
```

    # The semaphore is now at 2

#### 4.3.4 Event Tests

```python
import pytest
import anyio
from pynector.concurrency.primitives import Event
from pynector.concurrency.task import create_task_group

@pytest.mark.asyncio
async def test_event_basic():
    """Test basic event functionality."""
    event = Event()
    
    # Test initial state
    assert not event.is_set()
    
    # Test setting the event
    event.set()
    assert event.is_set()
    
    # Test waiting for the event
    await event.wait()  # Should return immediately

@pytest.mark.asyncio
async def test_event_wait():
    """Test waiting for an event."""
    event = Event()
    results = []
    
    async def waiter(task_id):
        results.append(f"waiting-{task_id}")
        await event.wait()
        results.append(f"done-{task_id}")
    
    async with create_task_group() as tg:
        await tg.start_soon(waiter, 1)
        await tg.start_soon(waiter, 2)
        await anyio.sleep(0.1)  # Give waiters time to start
        
        # Both waiters should be waiting
        assert results == ["waiting-1", "waiting-2"]
        
        # Set the event
        event.set()
    
    # Both waiters should be done
    assert "done-1" in results
    assert "done-2" in results
```

#### 4.3.5 Condition Tests

```python
import pytest
import anyio
from pynector.concurrency.primitives import Condition, Lock
from pynector.concurrency.task import create_task_group

@pytest.mark.asyncio
async def test_condition_basic():
    """Test basic condition functionality."""
    condition = Condition()
    
    # Test that the condition can be acquired and released
    async with condition:
        # We have the lock
        pass
    # The lock is released

@pytest.mark.asyncio
async def test_condition_wait_notify():
    """Test condition wait and notify."""
    condition = Condition()
    results = []
    
    async def waiter(task_id):
        async with condition:
            results.append(f"waiting-{task_id}")
            await condition.wait()
            results.append(f"notified-{task_id}")
    
    async def notifier():
        await anyio.sleep(0.1)  # Give waiters time to start
        async with condition:
            results.append("notifying-1")
            await condition.notify()
        
        await anyio.sleep(0.1)  # Give the first waiter time to process
        async with condition:
            results.append("notifying-all")
            await condition.notify_all()
    
    async with create_task_group() as tg:
        await tg.start_soon(waiter, 1)
        await tg.start_soon(waiter, 2)
        await tg.start_soon(waiter, 3)
        await tg.start_soon(notifier)
    
    # Check the sequence of events
    assert results.index("waiting-1") < results.index("notifying-1")
    assert results.index("waiting-2") < results.index("notifying-1")
    assert results.index("waiting-3") < results.index("notifying-1")
    
    assert results.index("notifying-1") < results.index("notified-1")
    assert results.index("notifying-all") < results.index("notified-2")
    assert results.index("notifying-all") < results.index("notified-3")
```

### 4.4 Error Handling Tests (`test_errors.py`)

These tests will verify that the error handling utilities correctly handle
cancellation and other errors.

````python
import pytest
import anyio
from pynector.concurrency.errors import get_cancelled_exc_class, shield
from pynector.concurrency.cancel import move_on_after

@pytest.mark.asyncio
async def test_get_cancelled_exc_class():
    """Test that get_cancelled_exc_class returns the correct exception class."""
    exc_class = get_cancelled_exc_class()
    assert exc_class is anyio.get_cancelled_exc_class()

@pytest.mark.asyncio
async def test_shield():
    """Test that shield protects operations from cancellation."""
    results = []
    
    async def shielded_operation():
        await anyio.sleep(0.2)
        results.append("shielded_completed")
        return "shielded_result"
    
    async def task():
        try:
            await anyio.sleep(0.5)
            results.append("task_completed")
        except get_cancelled_exc_class():
            results.append("task_cancelled")
            result = await shield(shielded_operation)
            assert result == "shielded_result"
            raise
    
    with move_on_after(0.1) as scope:
        try:
            await task()
        except get_cancelled_exc_class():
            results.append("caught")
    
    assert "task_cancelled" in results
    assert "shielded_completed" in results
    assert "task_completed" not in results
### 4.5 Concurrency Pattern Tests (`test_patterns.py`)

These tests will verify that the concurrency patterns correctly implement common patterns for structured concurrency.

#### 4.5.1 Connection Pool Tests

```python
import pytest
import anyio
from pynector.concurrency.patterns import ConnectionPool
from pynector.concurrency.task import create_task_group

@pytest.mark.asyncio
async def test_connection_pool_basic():
    """Test basic connection pool functionality."""
    connections_created = 0
    
    class MockConnection:
        def __init__(self, id):
            self.id = id
            self.closed = False
        
        async def close(self):
            self.closed = True
    
    async def connection_factory():
        nonlocal connections_created
        connections_created += 1
        return MockConnection(connections_created)
    
    pool = ConnectionPool(max_connections=2, connection_factory=connection_factory)
    
    # Test acquiring connections
    conn1 = await pool.acquire()
    assert conn1.id == 1
    assert connections_created == 1
    
    conn2 = await pool.acquire()
    assert conn2.id == 2
    assert connections_created == 2
    
    # Release a connection back to the pool
    await pool.release(conn1)
    
    # Acquiring again should reuse the released connection
    conn3 = await pool.acquire()
    assert conn3.id == 1  # Reused connection
    assert connections_created == 2  # No new connection created
    
    # Test async context manager
    async with pool:
        pass
    
    # All connections should be closed
    assert conn2.closed
    assert conn3.closed

@pytest.mark.asyncio
async def test_connection_pool_contention():
    """Test that connection pools properly handle contention."""
    connections_created = 0
    
    class MockConnection:
        def __init__(self, id):
            self.id = id
            self.closed = False
        
        async def close(self):
            self.closed = True
    
    async def connection_factory():
        nonlocal connections_created
        connections_created += 1
        await anyio.sleep(0.05)  # Simulate connection time
        return MockConnection(connections_created)
    
    pool = ConnectionPool(max_connections=2, connection_factory=connection_factory)
    results = []
    
    async def worker(worker_id):
        conn = await pool.acquire()
        results.append(f"acquired-{worker_id}-{conn.id}")
        await anyio.sleep(0.1)  # Simulate work
        await pool.release(conn)
        results.append(f"released-{worker_id}-{conn.id}")
    
    async with pool:
        async with create_task_group() as tg:
            for i in range(5):
                await tg.start_soon(worker, i)
    
    # Only 2 connections should have been created
    assert connections_created == 2
    
    # All workers should have completed
    assert len(results) == 10
    
    # Check that connections were reused
    conn_ids = [int(r.split('-')[-1]) for r in results if r.startswith('acquired')]
    assert len(conn_ids) == 5
    assert max(conn_ids) == 2
````

#### 4.5.2 Parallel Request Tests

```python
import pytest
import anyio
from pynector.concurrency.patterns import parallel_requests

@pytest.mark.asyncio
async def test_parallel_requests_basic():
    """Test basic parallel request functionality."""
    urls = ["url1", "url2", "url3", "url4", "url5"]
    
    async def fetch(url):
        await anyio.sleep(0.1)  # Simulate network delay
        return f"response-{url}"
    
    responses = await parallel_requests(urls, fetch, max_concurrency=2)
    
    # All URLs should have been fetched
    assert len(responses) == 5
    assert responses == ["response-url1", "response-url2", "response-url3", "response-url4", "response-url5"]

@pytest.mark.asyncio
async def test_parallel_requests_error():
    """Test error handling in parallel requests."""
    urls = ["url1", "url2", "error", "url4", "url5"]
    
    async def fetch(url):
        await anyio.sleep(0.1)  # Simulate network delay
        if url == "error":
            raise ValueError("Fetch error")
        return f"response-{url}"
    
    with pytest.raises(ValueError, match="Fetch error"):
        await parallel_requests(urls, fetch, max_concurrency=2)
```

#### 4.5.3 Timeout Retry Tests

```python
import pytest
import anyio
from pynector.concurrency.patterns import retry_with_timeout

@pytest.mark.asyncio
async def test_retry_with_timeout_success():
    """Test successful retry with timeout."""
    attempts = 0
    
    async def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            await anyio.sleep(0.2)  # This will time out
        return "success"
    
    result = await retry_with_timeout(
        operation,
        max_retries=3,
        timeout=0.1
    )
    
    assert attempts == 3
    assert result == "success"

@pytest.mark.asyncio
async def test_retry_with_timeout_all_timeout():
    """Test retry with all attempts timing out."""
    attempts = 0
    
    async def operation():
        nonlocal attempts
        attempts += 1
        await anyio.sleep(0.2)  # This will always time out
        return "success"
    
    with pytest.raises(TimeoutError):
        await retry_with_timeout(
            operation,
            max_retries=3,
            timeout=0.1
        )
    
    assert attempts == 3
```

#### 4.5.4 Worker Pool Tests

```python
import pytest
import anyio
from pynector.concurrency.patterns import WorkerPool

@pytest.mark.asyncio
async def test_worker_pool_basic():
    """Test basic worker pool functionality."""
    results = []
    
    async def worker_func(item):
        await anyio.sleep(0.1)  # Simulate work
        results.append(item)
    
    pool = WorkerPool(num_workers=2, worker_func=worker_func)
    
    # Start the pool
    await pool.start()
    
    # Submit items
    await pool.submit(1)
    await pool.submit(2)
    await pool.submit(3)
    await pool.submit(4)
    await pool.submit(5)
    
    # Wait for all items to be processed
    await anyio.sleep(0.3)
    
    # Stop the pool
    await pool.stop()
    
    # All items should have been processed
    assert sorted(results) == [1, 2, 3, 4, 5]
```

### 4.6 Integration Tests (`test_integration.py`)

These tests will verify that all components work together correctly.

```python
import pytest
import anyio
from pynector.concurrency.task import create_task_group
from pynector.concurrency.cancel import move_on_after, fail_after
from pynector.concurrency.primitives import Lock, Semaphore, CapacityLimiter, Event, Condition
from pynector.concurrency.patterns import ConnectionPool, parallel_requests, retry_with_timeout, WorkerPool

@pytest.mark.asyncio
async def test_task_group_with_cancellation():
    """Test task groups with cancellation."""
    results = []
    
    async def task(task_id):
        try:
            await anyio.sleep(0.5)
            results.append(f"completed-{task_id}")
        except anyio.get_cancelled_exc_class():
            results.append(f"cancelled-{task_id}")
            raise
    
    with move_on_after(0.2) as scope:
        async with create_task_group() as tg:
            await tg.start_soon(task, 1)
            await tg.start_soon(task, 2)
            await tg.start_soon(task, 3)
    
    # All tasks should have been cancelled
    assert "cancelled-1" in results
    assert "cancelled-2" in results
    assert "cancelled-3" in results
    assert "completed-1" not in results
    assert "completed-2" not in results
    assert "completed-3" not in results

@pytest.mark.asyncio
async def test_resource_primitives_integration():
    """Test integration of resource primitives."""
    lock = Lock()
    semaphore = Semaphore(2)
    event = Event()
    results = []
    
    async def worker(worker_id):
        # First acquire the semaphore (max 2 concurrent)
        async with semaphore:
            results.append(f"semaphore-acquired-{worker_id}")
            
            # Then acquire the lock (one at a time)
            async with lock:
                results.append(f"lock-acquired-{worker_id}")
                await anyio.sleep(0.1)
                results.append(f"lock-released-{worker_id}")
            
            # Wait for the event
            await event.wait()
            results.append(f"event-received-{worker_id}")
    
    async with create_task_group() as tg:
        for i in range(5):
            await tg.start_soon(worker, i)
        
        # Give workers time to start
        await anyio.sleep(0.3)
        
        # Set the event to release all waiting workers
        event.set()
    
    # Check that the semaphore limited concurrency
    semaphore_acquired = [i for i, r in enumerate(results) if "semaphore-acquired" in r]
    assert len(semaphore_acquired) == 5
    
    # Check that the lock ensured mutual exclusion
    lock_acquired = [i for i, r in enumerate(results) if "lock-acquired" in r]
    lock_released = [i for i, r in enumerate(results) if "lock-released" in r]
    for i in range(len(lock_acquired) - 1):
        assert lock_released[i] < lock_acquired[i + 1]
    
    # Check that all workers received the event
    event_received = [i for i, r in enumerate(results) if "event-received" in r]
    assert len(event_received) == 5
```

## 5. Test Coverage

The tests are designed to achieve >80% code coverage across all components.
Coverage will be measured using pytest-cov and reported during CI runs.

```bash
pytest --cov=pynector.concurrency tests/concurrency/
```

## 6. Test Execution

Tests will be executed as part of the CI pipeline and can also be run locally
using pytest:

```bash
# Run all tests
pytest tests/concurrency/

# Run specific test file
pytest tests/concurrency/test_task.py

# Run with coverage
pytest --cov=pynector.concurrency tests/concurrency/

# Generate coverage report
pytest --cov=pynector.concurrency --cov-report=html tests/concurrency/
```

## 7. References

1. Technical Design Specification: Structured Concurrency (TDS-2.md) (search:
   internal-document)
2. Implementation Plan: Structured Concurrency (IP-2.md) (search:
   internal-document)
3. AnyIO Documentation (search: exa-anyio.readthedocs.io)
4. AnyIO Tasks Documentation (search:
   exa-anyio.readthedocs.io/en/latest/tasks.html)
5. AnyIO Cancellation Documentation (search:
   exa-anyio.readthedocs.io/en/stable/cancellation.html)
6. AnyIO Synchronization Documentation (search:
   exa-anyio.readthedocs.io/en/stable/synchronization.html)
7. pytest Documentation (search: exa-docs.pytest.org)
8. pytest-asyncio Documentation (search: exa-pytest-asyncio.readthedocs.io)
