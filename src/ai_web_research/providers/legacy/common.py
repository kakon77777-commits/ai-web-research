from __future__ import annotations

import datetime as dt
from dataclasses import asdict, is_dataclass
from typing import Any

from ai_web_research.core.types import SearchAction
from ai_web_research.execution.models import ExecutionContext


class LegacyAdapterError(RuntimeError):
    pass


def occurred_at(context: ExecutionContext) -> str:
    clock = context.services.get("clock")
    if callable(clock):
        return str(clock())
    return dt.datetime.now(dt.timezone.utc).isoformat()


def require_service(context: ExecutionContext, name: str) -> object:
    try:
        return context.services[name]
    except KeyError as exc:
        raise LegacyAdapterError(f"missing execution service: {name}") from exc


def validate_action(
    action: SearchAction,
    *,
    method_id: str,
    provider_id: str,
    surface_id: str,
    binding_id: str,
) -> None:
    actual = (
        action.method_ref.id,
        action.provider_ref.id,
        action.surface_id,
        action.binding_id,
    )
    expected = (method_id, provider_id, surface_id, binding_id)
    if actual != expected:
        raise LegacyAdapterError(f"action contract mismatch: expected {expected}, got {actual}")


def jsonable(value: Any):
    if is_dataclass(value):
        return {k: jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
