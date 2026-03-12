"""Event helpers for async callbacks."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from types import MethodType
from typing import Any
import weakref


class Event:
    """Async event with weak-referenced subscribers."""

    def __init__(self) -> None:
        self._handlers: list[weakref.ReferenceType] = []

    def __iadd__(self, handler: Callable[..., Any]) -> "Event":
        if isinstance(handler, MethodType):
            ref = weakref.WeakMethod(handler)
        else:
            ref = weakref.ref(handler)
        self._handlers.append(ref)
        return self

    def __isub__(self, handler: Callable[..., Any]) -> "Event":
        self._handlers = [ref for ref in self._handlers if ref() is not handler]
        return self

    async def __call__(self, *args: Any, **kwargs: Any) -> None:
        tasks = []
        for ref in self._handlers:
            func = ref()
            if func is not None:
                tasks.append(func(*args, **kwargs))
        if tasks:
            await asyncio.gather(*tasks)

        self._handlers = [ref for ref in self._handlers if ref() is not None]


class DataEvent:
    """Data event helper with async dispatch."""

    def __init__(self) -> None:
        self.on_data_event = Event()

    async def data_event(self, data: Any | None = None) -> None:
        """Execute the data event callbacks."""
        if data is None:
            await self.on_data_event()
        else:
            await self.on_data_event(data)

    def add_subscribers(self, obj_method: Callable[..., Any]) -> None:
        """Add subscribers."""
        self.on_data_event += obj_method

    def remove_subscribers(self, obj_method: Callable[..., Any]) -> None:
        """Remove subscribers."""
        try:
            self.on_data_event -= obj_method
        except ValueError:
            pass
