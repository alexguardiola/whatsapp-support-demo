import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


class UsageCap:
    """Daily ceiling on model calls and tokens. When it is reached the bot stops and humans take over."""

    def __init__(self, path: str | Path, max_calls_per_day: int, max_tokens_per_day: int, tz: str = "Europe/Madrid"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_calls, self.max_tokens, self.tz = max_calls_per_day, max_tokens_per_day, ZoneInfo(tz)
        with self._db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS usage (day TEXT PRIMARY KEY, calls INTEGER, tokens INTEGER)")

    def _db(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, isolation_level="IMMEDIATE", timeout=5)

    def _day(self, when: datetime) -> str:
        return when.astimezone(self.tz).date().isoformat()

    def try_consume(self, when: datetime) -> bool:
        day = self._day(when)
        with self._db() as db:
            row = db.execute("SELECT calls, tokens FROM usage WHERE day = ?", (day,)).fetchone() or (0, 0)
            if row[0] >= self.max_calls or row[1] >= self.max_tokens:
                return False
            db.execute(
                "INSERT INTO usage VALUES (?, 1, 0) ON CONFLICT(day) DO UPDATE SET calls = calls + 1", (day,)
            )
        return True

    def record_tokens(self, when: datetime, tokens: int) -> None:
        with self._db() as db:
            db.execute(
                "INSERT INTO usage VALUES (?, 0, ?) ON CONFLICT(day) DO UPDATE SET tokens = tokens + excluded.tokens",
                (self._day(when), tokens),
            )

    def snapshot(self, when: datetime) -> dict[str, int]:
        with self._db() as db:
            row = db.execute("SELECT calls, tokens FROM usage WHERE day = ?", (self._day(when),)).fetchone() or (0, 0)
        return {"calls": row[0], "tokens": row[1]}
