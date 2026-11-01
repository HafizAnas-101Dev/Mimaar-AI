"""Local SQLite history of past analyses."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .schemas import AnalysisResult, HistoryEntry, Report, RoomResult


class History:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, created_at TEXT NOT NULL,
                    title TEXT NOT NULL, summary TEXT NOT NULL, currency TEXT NOT NULL,
                    low REAL, high REAL, body TEXT NOT NULL)"""
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def add(self, result: AnalysisResult | RoomResult) -> None:
        kind = "room" if isinstance(result, RoomResult) else "photo"
        title = (
            f"Room ({len(result.photos)} photos)" if isinstance(result, RoomResult) else result.filename or "Photo"
        )
        report: Report = result.report
        cost = report.cost_estimate
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO analyses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    result.id,
                    kind,
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    title,
                    report.summary,
                    cost.currency,
                    cost.low,
                    cost.high,
                    result.model_dump_json(),
                ),
            )

    def update(self, result: AnalysisResult | RoomResult) -> None:
        """Store a changed result in place, keeping its date and position in the list."""
        with self._connect() as db:
            db.execute(
                "UPDATE analyses SET summary = ?, body = ? WHERE id = ?",
                (result.report.summary, result.model_dump_json(), result.id),
            )

    def rename(self, entry_id: str, title: str) -> bool:
        with self._connect() as db:
            return db.execute("UPDATE analyses SET title = ? WHERE id = ?", (title, entry_id)).rowcount > 0

    def clear(self) -> int:
        with self._connect() as db:
            return db.execute("DELETE FROM analyses").rowcount

    def list(self, limit: int = 50) -> list[HistoryEntry]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT id, kind, created_at, title, summary, currency, low, high FROM analyses "
                "ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
        keys = ("id", "kind", "created_at", "title", "summary", "currency", "low", "high")
        return [HistoryEntry(**dict(zip(keys, row))) for row in rows]

    def get(self, entry_id: str) -> AnalysisResult | RoomResult | None:
        with self._connect() as db:
            row = db.execute("SELECT kind, body FROM analyses WHERE id = ?", (entry_id,)).fetchone()
        if not row:
            return None
        model = RoomResult if row[0] == "room" else AnalysisResult
        return model.model_validate_json(row[1])

    def delete(self, entry_id: str) -> bool:
        with self._connect() as db:
            return db.execute("DELETE FROM analyses WHERE id = ?", (entry_id,)).rowcount > 0
