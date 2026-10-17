"""Append-only JSONL log of questions and outcomes.

Two uses:
- Docs gap report: questions the docs could not answer, most frequent first,
  so the support team knows which articles to write next.
- Quality monitoring: refusal rate, feedback, latency.

Emails and long digit runs are redacted before writing. In production this would
go to a proper store (Postgres / log pipeline) with a retention policy.
"""
import json
import re
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_LONG_NUMBER = re.compile(r"\b\d{6,}\b")


def redact(text: str) -> str:
    return _LONG_NUMBER.sub("[number]", _EMAIL.sub("[email]", text))


class QueryLog:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: dict) -> None:
        record = {"ts": datetime.now(timezone.utc).isoformat(), **record}
        if "question" in record:
            record["question"] = redact(record["question"])
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def _records(self):
        if not self.path.exists():
            return
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    def gaps(self, limit: int = 20) -> list[dict]:
        counts = Counter(
            r["question"].strip().lower()
            for r in self._records()
            if r.get("type") == "ask" and r.get("status") == "not_covered"
        )
        return [{"question": q, "count": n} for q, n in counts.most_common(limit)]
