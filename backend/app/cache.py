"""File cache for model responses so reruns and the live demo cost no credits."""
import hashlib
import json
from pathlib import Path
from typing import Any


class ResponseCache:
    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(*parts: str | bytes) -> str:
        h = hashlib.sha256()
        for part in parts:
            h.update(part if isinstance(part, bytes) else part.encode("utf-8"))
            h.update(b"\x00")
        return h.hexdigest()

    def get(self, key: str) -> Any | None:
        path = self.directory / f"{key}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def set(self, key: str, value: Any) -> None:
        path = self.directory / f"{key}.json"
        path.write_text(json.dumps(value), encoding="utf-8")
