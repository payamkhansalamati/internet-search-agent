import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class RequestRecord:
    stage: str
    created_at: datetime
    updated_at: datetime
    result: Any = None
    error: str | None = None


class StatusStore:
    def __init__(self) -> None:
        self._items: dict[str, RequestRecord] = {}
        self._lock = threading.RLock()

    def create(self, request_id: str) -> None:
        now = datetime.now(UTC)
        with self._lock:
            self._items[request_id] = RequestRecord("received", now, now)

    def update(self, request_id: str, stage: str, *, result: Any = None, error: str | None = None) -> None:
        with self._lock:
            record = self._items[request_id]
            record.stage, record.updated_at, record.result, record.error = stage, datetime.now(UTC), result, error

    def get(self, request_id: str) -> RequestRecord | None:
        with self._lock:
            return self._items.get(request_id)
