from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from mci_client.models import ReconciliationReport


def _now_iso() -> str:
    return datetime.now(ZoneInfo("Asia/Tehran")).isoformat()


class RecordWriter:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def write_record(self, report: ReconciliationReport) -> None:
        record = {
            "timestamp": _now_iso(),
            "group_id": report.group_id,
            "state": report.state.value,
            "used_rounds": report.used_rounds,
            "converged": report.converged,
            "failures": report.failures,
            "meta": report.meta,
        }
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            f.write(line)