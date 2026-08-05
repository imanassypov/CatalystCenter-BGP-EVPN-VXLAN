"""In-memory session for the single-user editor."""

from __future__ import annotations

from typing import Any


class SessionStore:
    def __init__(self) -> None:
        self._session: dict[str, Any] | None = None

    @property
    def loaded(self) -> bool:
        return self._session is not None

    def get(self) -> dict[str, Any] | None:
        return self._session

    def set(self, session: dict[str, Any]) -> None:
        self._session = session

    def clear(self) -> None:
        self._session = None
