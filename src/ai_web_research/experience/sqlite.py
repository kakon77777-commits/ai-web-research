from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ai_web_research.core.types import VersionRef
from ai_web_research.execution.models import ObservationStatus, PolicyDecision

from .receipt import SearchActionReceipt, SearchReceipt, SearchReceiptStatus


class ReceiptStoreConflict(ValueError):
    pass


_SCHEMA = """
CREATE TABLE IF NOT EXISTS search_action_receipts (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    action_receipt_id TEXT UNIQUE NOT NULL,
    task_id TEXT NOT NULL,
    epoch_id TEXT NOT NULL,
    action_id TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_search_action_receipts_epoch
ON search_action_receipts(epoch_id, sequence);

CREATE TABLE IF NOT EXISTS search_receipts (
    receipt_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    epoch_id TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
"""


def _canonical(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_canonical(v) for v in value]
    if hasattr(value, "__dataclass_fields__"):
        return {name: _canonical(getattr(value, name)) for name in value.__dataclass_fields__}
    raise TypeError(type(value).__name__)


def _dump(value) -> str:
    return json.dumps(_canonical(value), ensure_ascii=False, sort_keys=True)


class SearchReceiptStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def save_search_action_receipt(self, receipt: SearchActionReceipt) -> None:
        payload = _dump(receipt)
        row = self._conn.execute(
            "SELECT payload_json FROM search_action_receipts WHERE action_receipt_id=?",
            (receipt.action_receipt_id,),
        ).fetchone()
        if row is not None:
            if row["payload_json"] == payload:
                return
            raise ReceiptStoreConflict(
                f"conflicting search action receipt {receipt.action_receipt_id}"
            )
        self._conn.execute(
            """
            INSERT INTO search_action_receipts
                (action_receipt_id, task_id, epoch_id, action_id, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                receipt.action_receipt_id,
                receipt.task_id,
                receipt.epoch_id,
                receipt.action_id,
                payload,
            ),
        )
        self._conn.commit()

    @staticmethod
    def _decode_action(data: dict) -> SearchActionReceipt:
        return SearchActionReceipt(
            action_receipt_id=data["action_receipt_id"],
            task_id=data["task_id"],
            epoch_id=data["epoch_id"],
            action_id=data["action_id"],
            method_ref=VersionRef(data["method_ref"]["id"], data["method_ref"]["version"]),
            provider_ref=VersionRef(data["provider_ref"]["id"], data["provider_ref"]["version"]),
            surface_id=data["surface_id"],
            binding_id=data["binding_id"],
            policy_decision=PolicyDecision(data["policy_decision"]),
            policy_refs=tuple(data["policy_refs"]),
            reason_codes=tuple(data["reason_codes"]),
            observation_id=data["observation_id"],
            observation_status=(
                ObservationStatus(data["observation_status"])
                if data["observation_status"] is not None
                else None
            ),
            result_count=data["result_count"],
            artifact_refs=tuple(data["artifact_refs"]),
            cost=data["cost"],
            latency_ms=data["latency_ms"],
            gap_refs=tuple(data["gap_refs"]),
            occurred_at=data["occurred_at"],
            metadata=data["metadata"],
        )

    def list_search_action_receipts(
        self, epoch_id: str
    ) -> tuple[SearchActionReceipt, ...]:
        rows = self._conn.execute(
            """
            SELECT payload_json FROM search_action_receipts
            WHERE epoch_id=? ORDER BY sequence ASC
            """,
            (epoch_id,),
        ).fetchall()
        return tuple(
            self._decode_action(json.loads(row["payload_json"]))
            for row in rows
        )

    def save_search_receipt(self, receipt: SearchReceipt) -> None:
        payload = _dump(receipt)
        row = self._conn.execute(
            "SELECT payload_json FROM search_receipts WHERE receipt_id=?",
            (receipt.receipt_id,),
        ).fetchone()
        if row is not None:
            if row["payload_json"] == payload:
                return
            raise ReceiptStoreConflict(f"conflicting search receipt {receipt.receipt_id}")
        self._conn.execute(
            """
            INSERT INTO search_receipts (receipt_id, task_id, epoch_id, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (receipt.receipt_id, receipt.task_id, receipt.epoch_id, payload),
        )
        self._conn.commit()

    def get_search_receipt(self, receipt_id: str) -> SearchReceipt:
        row = self._conn.execute(
            "SELECT payload_json FROM search_receipts WHERE receipt_id=?",
            (receipt_id,),
        ).fetchone()
        if row is None:
            raise KeyError(receipt_id)
        data = json.loads(row["payload_json"])
        return SearchReceipt(
            receipt_id=data["receipt_id"],
            task_id=data["task_id"],
            epoch_id=data["epoch_id"],
            registry_snapshot_id=data["registry_snapshot_id"],
            planner_id=data["planner_id"],
            planner_version=data["planner_version"],
            actions=tuple(self._decode_action(item) for item in data["actions"]),
            stop_reason=data["stop_reason"],
            status=SearchReceiptStatus(data["status"]),
            created_at=data["created_at"],
            metadata=data["metadata"],
        )
