# Research Report: Structured Concurrency Patterns in AnyIO

**Issue:** #2\
**Author:** pynector-researcher\
**Date:** 2025-05-05\
**Status:** Complete

## 1. Executive Summary

This research report explores structured concurrency patterns in AnyIO, focusing
on task groups, cancellation scopes, and resource management primitives. The
goal is to provide a solid foundation for implementing robust concurrent code in
the pynector project that follows best practices for error propagation and
timeout handling.

Key findings:

- AnyIO implements trio-like structured concurrency on top of asyncio, providing
  a consistent API that works with either backend
- Task groups enforce proper cleanup and error propagation, ensuring all child
  tasks are properly managed
- Cancellation scopes provide fine-grained control over task cancellation and
  timeouts
- Resource management primitives like Lock and CapacityLimiter help coordinate
  access to shared resources
- Error handling in AnyIO follows structured concurrency principles, with proper
  propagation of exceptions

## 2. Structured Concurrency in AnyIO

### 2.1 Core Principles

Structured concurrency is a programming paradigm that ensures tasks have
well-defined lifetimes and proper cleanup. AnyIO implements this paradigm by
enforcing several key principles:

1. **Task Hierarchy**: Tasks are organized in a parent-child relationship, where
   parent tasks are responsible for their children
2. **Bounded Lifetimes**: Child tasks cannot outlive their parent scope
3. **Error Propagation**: Errors in child tasks propagate to the parent
4. **Automatic Cleanup**: Resources are properly released when tasks complete or
   fail

AnyIO brings these principles to asyncio while maintaining compatibility with
trio's native structured concurrency model.

**Source:** [AnyIO Documentation](https://anyio.readthedocs.io/) (search:
exa-anyio.readthedocs.io)

> "AnyIO is an asynchronous networking and concurrency library that works on top
> of either asyncio or trio. It implements trio-like structured concurrency (SC)
> on top of asyncio and works in harmony with the native SC of trio itself."

### 2.2 Comparison with Native asyncio

AnyIO's structured concurrency model differs significantly from native asyncio:

| Feature        | Native asyncio                           | AnyIO                                |
| -------------- | ---------------------------------------- | ------------------------------------ |
| Task creation  | `asyncio.create_task()`                  | `task_group.start_soon()`            |
| Error handling | Errors can be lost if not awaited        | Errors propagate to parent task      |
| Cancellation   | Edge-based (only affects current awaits) | State-based (affects all operations) |
| Cleanup        | Manual via try/finally                   | Automatic via task groups            |

**Source:**
[Stack Overflow - Difference between anyio.TaskGroup and asyncio.TaskGroup](https://stackoverflow.com/questions/78060510/what-is-the-difference-between-anyio-taskgroup-and-asyncio-taskgroup)
(search: exa-stackoverflow.com/questions/78060510)

> "In contrast, asyncio task groups use edge-based cancellation. This means that
> any currently active tasks (which must all be sitting in an `await`) will
> receive a cancellation exception, but then any future calls will continue as
> usual."

## 3. Task Groups

Task groups are the fundamental building block of structured concurrency in
AnyIO. They provide a way to spawn and manage multiple concurrent tasks while
ensuring proper cleanup and error propagation.

### 3.1 Creating and Managing Tasks

Task groups are implemented as asynchronous context managers that ensure all
child tasks are properly managed:

```python
async with anyio.create_task_group() as tg:
    await tg.start_soon(task_function, arg1, arg2)
    await tg.start_soon(another_task)
```

Key features of task groups:

1. **Bounded Lifetime**: All child tasks must complete before the context
   manager exits
2. **Automatic Cancellation**: If a child task raises an exception, all other
   child tasks are automatically cancelled
3. **Error Propagation**: Exceptions from child tasks propagate to the parent

**Source:**
[AnyIO Tasks Documentation](https://anyio.readthedocs.io/en/latest/tasks.html)
(search: exa-anyio.readthedocs.io/en/latest/tasks.html)

> "A task group is an asynchronous context manager that makes sure that all its
> child tasks are finished one way or another after the context block is exited.
> If a child task, or the code in the enclosed context block raises an
> exception, all child tasks are cancelled."

### 3.2 Task Initialization

AnyIO provides a mechanism for waiting until a task has successfully initialized
itself:

```python
async def server_task(task_status=anyio.TASK_STATUS_IGNORED):
    server = await start_server()
    await task_status.started(server.port)
    await server.serve()

async with anyio.create_task_group() as tg:
    port = await tg.start(server_task)
    # Now we know the server is running and we have its port
```

This pattern is particularly useful for services that need to perform
initialization before they're ready to handle requests.

**Source:**
[AnyIO Tasks Documentation](https://anyio.readthedocs.io/en/latest/tasks.html)
(search: exa-anyio.readthedocs.io/en/latest/tasks.html)

> "Sometimes it is very useful to be able to wait until a task has successfully
> initialized itself. For example, when starting network services, you can have
> your task start the listener and then signal the caller that initialization is
> done."

### 3.3 Error Handling in Task Groups

When multiple tasks raise exceptions in a task group, AnyIO collects them into
an `ExceptionGroup`:

```python
try:
    async with anyio.create_task_group() as tg:
        await tg.start_soon(task_that_might_fail)
        await tg.start_soon(another_task_that_might_fail)
except* Exception as eg:
    # Handle the exception group
```

This ensures that no exceptions are lost, even when multiple tasks fail
simultaneously.

**Source:**
[AnyIO Tasks Documentation](https://anyio.readthedocs.io/en/latest/tasks.html)
(search: exa-anyio.readthedocs.io/en/latest/tasks.html)

> "It is possible for more than one task to raise an exception in a task group.
> This can happen when a task reacts to cancellation by entering either an
> exception handler block or a `finally:` block and raises an exception there."

## 4. Cancellation and Timeouts

Cancellation is a key feature of asynchronous programming, allowing tasks to be
terminated gracefully when they're no longer needed or when they exceed a
timeout.

### 4.1 Cancellation Scopes

AnyIO uses cancel scopes to manage cancellation. Cancel scopes can be nested,
and cancelling a scope cancels all scopes nested within it:

```python
async with anyio.create_task_group() as tg:
    with anyio.CancelScope() as scope:
        await tg.start_soon(long_running_task)
        # Later...
        scope.cancel()  # Cancels all tasks in this scope
```

**Source:**
[AnyIO Cancellation Documentation](https://anyio.readthedocs.io/en/stable/cancellation.html)
(search: exa-anyio.readthedocs.io/en/stable/cancellation.html)

> "Cancel scopes are used as context managers and can be nested. Cancelling a
> cancel scope cancels all cancel scopes nested within it. If a task is waiting
> on something, it is cancelled immediately. If the task is just starting, it
> will run until it first tries to run an operation requiring waiting, such as
> `sleep()`."

### 4.2 Timeout Handling

AnyIO provides two main ways to implement timeouts:

1. **move_on_after**: Exits the context block after the specified timeout
   without raising an exception
2. **fail_after**: Raises a `TimeoutError` if the operation exceeds the
   specified timeout

```python
# Example with move_on_after
with anyio.move_on_after(5) as scope:
    await long_running_operation()
    if scope.cancelled_caught:
        print("Operation timed out")

# Example with fail_after
try:
    with anyio.fail_after(5):
        await long_running_operation()
except TimeoutError:
    print("Operation timed out")
```

**Source:**
[AnyIO Cancellation Documentation](https://anyio.readthedocs.io/en/stable/cancellation.html)
(search: exa-anyio.readthedocs.io/en/stable/cancellation.html)

> "Networked operations can often take a long time, and you usually want to set
> up some kind of a timeout to ensure that your application doesn't stall
> forever. There are two principal ways to do this: `move_on_after()` and
> `fail_after()`. Both are used as synchronous context managers. The difference
> between these two is that the former simply exits the context block
> prematurely on a timeout, while the other raises a `TimeoutError`."

### 4.3 Shielding from Cancellation

Sometimes tasks need to be protected from cancellation, particularly during
cleanup operations:

```python
async def cleanup_resources():
    with anyio.CancelScope(shield=True):
        await release_resources()  # This won't be cancelled
```

**Source:**
[AnyIO Cancellation Documentation](https://anyio.readthedocs.io/en/stable/cancellation.html)
(search: exa-anyio.readthedocs.io/en/stable/cancellation.html)

> "There are cases where you want to shield your task from cancellation, at
> least temporarily. The most important such use case is performing shutdown
> procedures on asynchronous resources."

### 4.4 Best Practices for Timeout Handling

1. **Use move_on_after for non-critical operations**: When the operation is
   optional or has a fallback
2. **Use fail_after for critical operations**: When the operation must succeed
   within the time limit
3. **Check cancelled_caught**: To determine if a timeout occurred with
   move_on_after
4. **Shield cleanup operations**: Ensure resource cleanup isn't interrupted by
   cancellation

**Source:**
[Asyncio Timeout Best Practices](https://superfastpython.com/asyncio-timeout-best-practices/)
(search: exa-superfastpython.com/asyncio-timeout-best-practices)

> "Timeouts provide a way to gracefully handle situations where an operation is
> expected to complete within a certain time frame but fails to do so. Instead
> of waiting indefinitely, you can catch a timeout exception and handle it
> appropriately."

## 5. Resource Management Primitives

AnyIO provides several synchronization primitives for managing access to shared
resources in concurrent code.

### 5.1 Lock

Locks ensure exclusive access to a shared resource:

```python
lock = anyio.Lock()

async def access_shared_resource():
    async with lock:
        # Access the shared resource safely
```

Locks in AnyIO are reentrant, meaning the same task can acquire the lock
multiple times without deadlocking.

**Source:**
[AnyIO Synchronization Documentation](https://anyio.readthedocs.io/en/stable/synchronization.html)
(search: exa-anyio.readthedocs.io/en/stable/synchronization.html)

> "Locks are used to guard shared resources to ensure sole access to a single
> task at once. They function much like semaphores with a maximum value of 1,
> except that only the task that acquired the lock can release it."

### 5.2 Semaphore

Semaphores limit the number of tasks that can access a resource simultaneously:

```python
semaphore = anyio.Semaphore(3)  # Allow up to 3 concurrent accesses

async def access_limited_resource():
    async with semaphore:
        # Access the resource (up to 3 tasks can be here at once)
```

**Source:**
[AnyIO Synchronization Documentation](https://anyio.readthedocs.io/en/stable/synchronization.html)
(search: exa-anyio.readthedocs.io/en/stable/synchronization.html)

> "Semaphores are used for limiting access to a shared resource. A semaphore
> starts with a maximum value, which is decremented each time the semaphore is
> acquired by a task and incremented when it is released. If the value drops to
> zero, any attempt to acquire the semaphore will block until another task
> releases it."

### 5.3 CapacityLimiter

CapacityLimiters are similar to semaphores but with an important difference:
they track which task acquired which slot, preventing a task from releasing a
slot it didn't acquire:

```python
limiter = anyio.CapacityLimiter(5)  # Allow up to 5 concurrent operations

async def limited_operation():
    async with limiter:
        # Perform the operation (up to 5 tasks can be here at once)
```

CapacityLimiters are particularly useful for limiting concurrency in worker
threads and network connections.

**Source:**
[AnyIO API Reference](https://anyio.readthedocs.io/en/latest/api.html) (search:
exa-anyio.readthedocs.io/en/latest/api.html)

> "CapacityLimiter objects are used to limit the number of concurrent
> operations."

### 5.4 Event

Events allow one task to signal one or more waiting tasks:

```python
event = anyio.Event()

async def waiter():
    await event.wait()
    print("Event was set!")

async def setter():
    await anyio.sleep(1)
    event.set()
```

Unlike standard library Events, AnyIO events cannot be reused and must be
replaced after being set.

**Source:**
[AnyIO Synchronization Documentation](https://anyio.readthedocs.io/en/stable/synchronization.html)
(search: exa-anyio.readthedocs.io/en/stable/synchronization.html)

> "Unlike standard library Events, AnyIO events cannot be reused, and must be
> replaced instead. This practice prevents a class of race conditions, and
> matches the behavior of Trio."

### 5.5 Condition

Conditions combine a lock and an event:

```python
condition = anyio.Condition()

async def producer():
    async with condition:
        # Modify shared state
        await condition.notify_all()

async def consumer():
    async with condition:
        await condition.wait()
        # Access updated shared state
```

**Source:**
[AnyIO Synchronization Documentation](https://anyio.readthedocs.io/en/stable/synchronization.html)
(search: exa-anyio.readthedocs.io/en/stable/synchronization.html)

> "A condition is basically a combination of an event and a lock. It first
> acquires a lock and then waits for a notification from the event. Once the
> condition receives a notification, it releases the lock."

## 6. Error Propagation

Proper error handling is crucial in concurrent code to ensure that failures are
properly detected and handled.

### 6.1 Exception Propagation in Task Groups

In AnyIO, exceptions from child tasks propagate to the parent task group:

```python
try:
    async with anyio.create_task_group() as tg:
        await tg.start_soon(task_that_might_fail)
except Exception as exc:
    # Handle the exception
```

If multiple tasks raise exceptions, they are collected into an `ExceptionGroup`.

**Source:**
[Mastering Exception Handling in Asynchronous Python](https://mysteryweevil.medium.com/mastering-exception-handling-in-asynchronous-python-a-practical-guide-75d9ae18939a)
(search:
exa-mysteryweevil.medium.com/mastering-exception-handling-in-asynchronous-python-a-practical-guide-75d9ae18939a)

> "When an exception occurs within a coroutine, it propagates through the
> coroutine chain, potentially causing unexpected behavior or even crashing your
> application if not handled properly."

### 6.2 Handling Cancellation Exceptions

Cancellation in AnyIO raises a cancellation exception that varies depending on
the backend. To catch this exception regardless of the backend, use
`get_cancelled_exc_class()`:

```python
from anyio import get_cancelled_exc_class

async def task_with_cleanup():
    try:
        await long_running_operation()
    except get_cancelled_exc_class():
        # Perform cleanup
        with anyio.CancelScope(shield=True):
            await cleanup_resources()
        raise  # Re-raise the cancellation exception
```

**Source:**
[AnyIO Cancellation Documentation](https://anyio.readthedocs.io/en/stable/cancellation.html)
(search: exa-anyio.readthedocs.io/en/stable/cancellation.html)

> "In some specific cases, you might only want to catch the cancellation
> exception. This is tricky because each async framework has its own exception
> class for that and AnyIO cannot control which exception is raised in the task
> when it's cancelled. To work around that, AnyIO provides a way to retrieve the
> exception class specific to the currently running async framework."

### 6.3 Best Practices for Error Handling

1. **Always re-raise cancellation exceptions**: Failing to do so may cause
   undefined behavior
2. **Shield cleanup operations**: Use `CancelScope(shield=True)` for cleanup
   that uses `await`
3. **Use try/except/finally blocks**: Ensure resources are properly cleaned up
   even on failure
4. **Handle ExceptionGroups**: Be prepared to handle multiple exceptions from
   task groups

**Source:**
[Structured Concurrency in Python with AnyIO](https://mattwestcott.org/blog/structured-concurrency-in-python-with-anyio)
(search: exa-mattwestcott.org/blog/structured-concurrency-in-python-with-anyio)

> "Failures in tasks should be handled by their parent: normally by propagating
> the exception after cancelling all siblings and cleaning up. Sometimes
> restarting the task is appropriate."

## 7. Recommendations for pynector

Based on the research, here are recommendations for implementing structured
concurrency in the pynector project:

### 7.1 Architecture

1. **Use task groups for concurrent operations**:
   - Organize related tasks in task groups
   - Let task groups handle cancellation and cleanup

2. **Implement proper timeout handling**:
   - Use `move_on_after` for non-critical operations
   - Use `fail_after` for operations that must complete within a time limit

3. **Adopt resource management primitives**:
   - Use `Lock` for exclusive access to resources
   - Use `CapacityLimiter` to control concurrency

### 7.2 Error Handling Strategy

1. **Propagate exceptions to appropriate level**:
   - Let task groups handle and propagate exceptions
   - Catch and handle exceptions at the appropriate level

2. **Implement proper cleanup**:
   - Use `finally` blocks for synchronous cleanup
   - Use shielded cancel scopes for asynchronous cleanup

3. **Handle cancellation gracefully**:
   - Catch cancellation exceptions using `get_cancelled_exc_class()`
   - Always re-raise cancellation exceptions after cleanup

### 7.3 Implementation Patterns

**Task Group Pattern**:

```python
async def main():
    async with anyio.create_task_group() as tg:
        await tg.start_soon(task1)
        await tg.start_soon(task2)
        # All tasks complete or are cancelled before exiting
```

**Timeout Pattern**:

```python
async def operation_with_timeout():
    with anyio.move_on_after(5) as scope:
        await long_running_operation()
        if scope.cancelled_caught:
            return fallback_result()
    return result
```

**Resource Management Pattern**:

```python
async def limited_concurrent_operations(urls):
    limiter = anyio.CapacityLimiter(10)  # Limit to 10 concurrent operations

    async def fetch_with_limit(url):
        async with limiter:
            return await fetch(url)

    async with anyio.create_task_group() as tg:
        for url in urls:
            await tg.start_soon(fetch_with_limit, url)
```

## 8. Conclusion

AnyIO provides a robust implementation of structured concurrency that works with
both asyncio and trio backends. By using task groups, cancellation scopes, and
resource management primitives, the pynector project can implement concurrent
code that is both efficient and reliable.

The key benefits of using AnyIO's structured concurrency patterns include:

1. **Improved reliability**: Proper error propagation and resource cleanup
2. **Better timeout handling**: Fine-grained control over timeouts and
   cancellation
3. **Simplified resource management**: Primitives for coordinating access to
   shared resources
4. **Consistent API**: Works with both asyncio and trio backends

By following the patterns and best practices outlined in this report, the
pynector project can implement robust concurrent code that avoids common
pitfalls like resource leaks, deadlocks, and lost exceptions.

## 9. References

1. AnyIO Documentation (search: exa-anyio.readthedocs.io)
2. AnyIO Tasks Documentation (search:
   exa-anyio.readthedocs.io/en/latest/tasks.html)
3. AnyIO Cancellation Documentation (search:
   exa-anyio.readthedocs.io/en/stable/cancellation.html)
4. AnyIO Synchronization Documentation (search:
   exa-anyio.readthedocs.io/en/stable/synchronization.html)
5. Structured Concurrency in Python with AnyIO (search:
   exa-mattwestcott.org/blog/structured-concurrency-in-python-with-anyio)
6. Stack Overflow - Difference between anyio.TaskGroup and asyncio.TaskGroup
   (search: exa-stackoverflow.com/questions/78060510)
7. Mastering Exception Handling in Asynchronous Python (search:
   exa-mysteryweevil.medium.com/mastering-exception-handling-in-asynchronous-python-a-practical-guide-75d9ae18939a)
8. Asyncio Timeout Best Practices (search:
   exa-superfastpython.com/asyncio-timeout-best-practices)
9. AnyIO: All You Need for Async Programming (search:
   exa-lewoudar.medium.com/anyio-all-you-need-for-async-programming-stuff-4cd084d0f6bd)
