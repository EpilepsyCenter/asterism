"""Undo stack for the document model (no Qt).

Commands are applied by `push` (which calls `redo`). The clean index marks the
state that matches the file on disk; `changed` fires on every push/undo/redo/clean
change so the app can refresh its Undo/Redo actions and the window's edited state.
"""

from __future__ import annotations

from .events import Signal


class Command:
    text = "Edit"

    def redo(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def undo(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class Macro(Command):
    """Several commands as one undo step."""

    def __init__(self, text: str, commands: list[Command] | None = None):
        self.text = text
        self.commands: list[Command] = list(commands or [])

    def redo(self) -> None:
        for c in self.commands:
            c.redo()

    def undo(self) -> None:
        for c in reversed(self.commands):
            c.undo()


class UndoStack:
    def __init__(self) -> None:
        self._cmds: list[Command] = []
        self._index = 0          # number of applied commands
        self._clean = 0          # index that matches disk; -1 = unreachable
        self.changed = Signal()

    # --- state ---------------------------------------------------------------

    @property
    def index(self) -> int:
        return self._index

    def count(self) -> int:
        return len(self._cmds)

    def can_undo(self) -> bool:
        return self._index > 0

    def can_redo(self) -> bool:
        return self._index < len(self._cmds)

    def undo_text(self) -> str:
        return self._cmds[self._index - 1].text if self.can_undo() else ""

    def redo_text(self) -> str:
        return self._cmds[self._index].text if self.can_redo() else ""

    def is_clean(self) -> bool:
        return self._index == self._clean

    def set_clean(self) -> None:
        self._clean = self._index
        self.changed.emit()

    # --- operations ----------------------------------------------------------

    def push(self, cmd: Command) -> None:
        cmd.redo()
        del self._cmds[self._index:]
        if self._clean > self._index:
            self._clean = -1
        self._cmds.append(cmd)
        self._index += 1
        self.changed.emit()

    def undo(self) -> None:
        if self.can_undo():
            self._index -= 1
            self._cmds[self._index].undo()
            self.changed.emit()

    def redo(self) -> None:
        if self.can_redo():
            self._cmds[self._index].redo()
            self._index += 1
            self.changed.emit()

    def clear(self) -> None:
        clean = self.is_clean()
        self._cmds.clear()
        self._index = 0
        self._clean = 0 if clean else -1
        self.changed.emit()
