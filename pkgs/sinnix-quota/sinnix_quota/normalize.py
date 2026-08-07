from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from . import SCHEMA

SECRET_WORDS = ("token", "secret", "cookie", "password", "apikey", "api_key")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def account_hash(value: Any) -> str | None:
    if value is None or not str(value).strip():
        return None
    digest = hashlib.sha256(str(value).strip().encode()).hexdigest()
    return f"sha256:{digest}"


def redact(value: Any, key: str = "") -> Any:
    lowered = key.lower()
    if any(word in lowered for word in SECRET_WORDS) or lowered in {
        "email",
        "account",
        "accountemail",
    }:
        return "[redacted]"
    if isinstance(value, dict):
        return {str(name): redact(item, str(name)) for name, item in value.items()}
    if isinstance(value, list):
        return [redact(item, key) for item in value]
    return value


def _fraction(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result > 1:
        result /= 100
    return result if 0 <= result <= 1 else None


def _entries(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        return [item for item in raw.get("data", []) if isinstance(item, dict)]
    return []


def _window(
    provider: str,
    account: Any,
    plan: Any,
    row: dict[str, Any],
    source: str,
    fetched_at: str,
) -> dict[str, Any]:
    used = _fraction(row.get("usedPercent"))
    remaining = _fraction(row.get("remainingPercent"))
    if remaining is None and used is not None:
        remaining = 1 - used
    return {
        "schema": SCHEMA,
        "kind": "provider_quota",
        "provider": provider,
        "account_hash": account_hash(account),
        "plan": plan,
        "plan_epoch": hashlib.sha256(
            f"{provider}|{account_hash(account)}|{plan}".encode()
        ).hexdigest()[:24],
        "window": {
            "name": row.get("name", "primary"),
            "duration_seconds": int(row["windowMinutes"] * 60)
            if row.get("windowMinutes") is not None
            else None,
            "used_fraction": used,
            "remaining_fraction": remaining,
            "resets_at": row.get("resetsAt"),
        },
        "native_units": {"unit": "fraction", "used": used, "remaining": remaining},
        "source": source,
        "fetched_at": fetched_at,
        "stale_after_seconds": 900,
        "confidence": "observed" if remaining is not None else "unavailable",
        "coverage": "provider_window" if remaining is not None else "missing_window",
        "uncertainty": None
        if remaining is not None
        else "provider did not publish a usable remaining fraction",
    }


def normalize_usage(
    raw: dict[str, Any], source: str, fetched_at: str | None = None
) -> list[dict[str, Any]]:
    fetched = (
        fetched_at
        or (raw.get("generatedAt") if isinstance(raw, dict) else None)
        or (raw.get("generated_at") if isinstance(raw, dict) else None)
        or _now()
    )
    rows: list[dict[str, Any]] = []
    for entry in _entries(raw):
        provider = str(entry.get("provider", "unknown"))
        account = entry.get("account") or (entry.get("usage") or {}).get(
            "identity", {}
        ).get("accountEmail")
        plan = (
            entry.get("plan")
            or (entry.get("usage") or {}).get("identity", {}).get("plan")
            or (entry.get("usage") or {}).get("loginMethod")
        )
        usage = entry.get("usage") or {}
        for name, key in (
            ("primary", "primary"),
            ("secondary", "secondary"),
            ("tertiary", "tertiary"),
        ):
            window = usage.get(key)
            if isinstance(window, dict):
                rows.append(
                    _window(
                        provider,
                        account,
                        plan,
                        {"name": name, **window},
                        source,
                        fetched,
                    )
                )
        credits = entry.get("credits")
        if isinstance(credits, dict) and credits.get("remaining") is not None:
            rows.append(
                {
                    "schema": SCHEMA,
                    "kind": "provider_quota",
                    "provider": provider,
                    "account_hash": account_hash(account),
                    "plan": plan,
                    "plan_epoch": hashlib.sha256(
                        f"{provider}|{account_hash(account)}|{plan}".encode()
                    ).hexdigest()[:24],
                    "window": {
                        "name": "credits",
                        "duration_seconds": None,
                        "used_fraction": None,
                        "remaining_fraction": None,
                        "resets_at": None,
                    },
                    "native_units": {
                        "unit": "credits",
                        "remaining": credits["remaining"],
                    },
                    "source": source,
                    "fetched_at": fetched,
                    "stale_after_seconds": 900,
                    "confidence": "observed",
                    "coverage": "provider_credits",
                    "uncertainty": None,
                }
            )
    return rows


def normalize_cost(
    raw: dict[str, Any], source: str, fetched_at: str | None = None
) -> list[dict[str, Any]]:
    fetched = (
        fetched_at
        or (raw.get("generatedAt") if isinstance(raw, dict) else None)
        or _now()
    )
    rows = []
    for entry in _entries(raw):
        totals = entry.get("totals") or {}
        rows.append(
            {
                "schema": SCHEMA,
                "kind": "calculated_cost",
                "provider": entry.get("provider", "unknown"),
                "account_hash": account_hash(entry.get("account")),
                "plan": None,
                "plan_epoch": None,
                "window": {
                    "name": "local_history",
                    "duration_seconds": None,
                    "used_fraction": None,
                    "remaining_fraction": None,
                    "resets_at": None,
                },
                "native_units": {
                    "unit": "tokens_and_usd",
                    "total_tokens": totals.get("totalTokens"),
                    "total_cost_usd": totals.get("totalCost"),
                },
                "source": source,
                "fetched_at": fetched,
                "stale_after_seconds": 3600,
                "confidence": "calculated",
                "coverage": "local_history",
                "uncertainty": "API-equivalent cost estimate; not provider quota",
            }
        )
    return rows


def compare(
    left: list[dict[str, Any]], right: list[dict[str, Any]], tolerance: float = 0.01
) -> list[dict[str, Any]]:
    by_key = {(row["provider"], row["window"]["name"]): row for row in left}
    disagreements = []
    for row in right:
        key = (row["provider"], row["window"]["name"])
        other = by_key.get(key)
        if not other:
            continue
        a = other["window"].get("remaining_fraction")
        b = row["window"].get("remaining_fraction")
        if a is not None and b is not None and abs(a - b) > tolerance:
            disagreements.append(
                {
                    "provider": key[0],
                    "window": key[1],
                    "left": other,
                    "right": row,
                    "resolution": "preserved_separately",
                }
            )
    return disagreements


def redact_json(raw: dict[str, Any]) -> dict[str, Any]:
    return redact(raw)
