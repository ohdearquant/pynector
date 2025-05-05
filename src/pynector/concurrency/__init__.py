"""Structured concurrency primitives for pynector.

This module provides structured concurrency primitives using AnyIO,
which allows for consistent behavior across asyncio and trio backends.
"""

from pynector.concurrency.task import TaskGroup, create_task_group
from pynector.concurrency.cancel import CancelScope, move_on_after, fail_after
from pynector.concurrency.primitives import (
    Lock, Semaphore, CapacityLimiter, Event, Condition
)
from pynector.concurrency.errors import get_cancelled_exc_class, shield

__all__ = [
    "TaskGroup",
    "create_task_group",
    "CancelScope",
    "move_on_after",
    "fail_after",
    "Lock",
    "Semaphore",
    "CapacityLimiter",
    "Event",
    "Condition",
    "get_cancelled_exc_class",
    "shield",
]