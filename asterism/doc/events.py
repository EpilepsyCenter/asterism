"""Plain-Python signals for the document model (no Qt).

Bound methods are held weakly, so a view that goes away is dropped automatically;
a Qt object whose C++ side was deleted (RuntimeError on call) is dropped too.
Plain functions and lambdas are held strongly — disconnect them explicitly.
"""

from __future__ import annotations

import inspect
import weakref
from typing import Callable


class Signal:
    __slots__ = ("_slots", "__weakref__")

    def __init__(self) -> None:
        self._slots: list[Callable[[], Callable | None]] = []

    def connect(self, fn) -> None:
        if isinstance(fn, Signal):
            fn = fn.emit
        if self._index(fn) >= 0:
            return
        if inspect.ismethod(fn):
            self._slots.append(weakref.WeakMethod(fn))
        else:
            self._slots.append(lambda fn=fn: fn)

    def disconnect(self, fn) -> None:
        if isinstance(fn, Signal):
            fn = fn.emit
        i = self._index(fn)
        if i >= 0:
            del self._slots[i]

    def _index(self, fn) -> int:
        for i, ref in enumerate(self._slots):
            if ref() == fn:
                return i
        return -1

    def emit(self, *args) -> None:
        for ref in list(self._slots):
            fn = ref()
            if fn is None:
                self._drop(ref)
                continue
            try:
                fn(*args)
            except RuntimeError as e:          # Qt object already deleted
                if "already deleted" not in str(e):
                    raise
                self._drop(ref)

    def _drop(self, ref) -> None:
        try:
            self._slots.remove(ref)
        except ValueError:
            pass

    def __len__(self) -> int:
        return sum(1 for r in self._slots if r() is not None)
