from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sinnix_agent_gateway.audit import AuditService
from sinnix_agent_gateway.capabilities import Principal
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.redaction import env_name_is_secret, redact, redact_env


def test_env_name_tokens_catch_missed_secret_names() -> None:
    assert env_name_is_secret("AIRVPN_SEED_KEY")
    assert env_name_is_secret("AIRVPN_SEED_PSK")
    assert env_name_is_secret("KAGGLE_KEY")
    assert env_name_is_secret("SINEX_LOCAL_DB")
    assert env_name_is_secret("GATEWAY_TOKEN")
    assert env_name_is_secret("OPENAI_API_KEY")
    assert not env_name_is_secret("KEYBOARD")
    assert not env_name_is_secret("PATH")
    assert not env_name_is_secret("PLAIN")


def test_redact_env_redacts_names_and_credential_shaped_values() -> None:
    env = redact_env(
        {
            "PLAIN": "value",
            "AIRVPN_SEED_KEY": "must-not-leak",
            "AIRVPN_SEED_PSK": "must-not-leak",
            "KAGGLE_KEY": "must-not-leak",
            "SINEX_LOCAL_DB": "/realm/state/sinex/local.db",
            "DATABASE_URL": "postgres://user:hunter2@localhost/db",
            "NOTE": "password=hunter2",
        }
    )
    assert env["PLAIN"] == "value"
    assert env["AIRVPN_SEED_KEY"] == "[REDACTED]"
    assert env["AIRVPN_SEED_PSK"] == "[REDACTED]"
    assert env["KAGGLE_KEY"] == "[REDACTED]"
    assert env["SINEX_LOCAL_DB"] == "[REDACTED]"
    assert env["DATABASE_URL"] == "[REDACTED]"
    assert env["NOTE"] == "[REDACTED]"
    assert redact("token=abc") == "token=[REDACTED]"


def test_audit_records_structured_diagnostics_and_redacts_values(
    tmp_path: Path,
) -> None:
    """Fails if a diagnostic string corrupts the audit row or a value leaks.

    Free-text redaction used to run over serialized JSON, where
    ``token=abc"`` swallowed the closing quote and the append raised.
    """
    audit = AuditService(
        GatewayConfig(state_dir=tmp_path / "state", projects={}),
        Principal.for_name("operator"),
    )
    receipt = audit.append(
        "fixture.call",
        "error",
        {
            "reason": "token=abc",
            "idempotency_key": "keep-1",
            "nested": {
                "password": "hunter2hunter2",
                "access_token": "synthetic-access-value",
                "note": "Authorization: Bearer synthetic-bearer-value",
                "rows": [{"secret": "synthetic-nested-secret", "count": 3}],
            },
        },
    )

    with sqlite3.connect(audit.path) as connection:
        (raw,) = connection.execute(
            "select payload_json from events where event_id = ?", (receipt["event_id"],)
        ).fetchone()
    stored = json.loads(raw)
    for value in (
        "hunter2hunter2",
        "synthetic-access-value",
        "synthetic-bearer-value",
        "synthetic-nested-secret",
    ):
        assert value not in raw
    assert stored["reason"] == "token=[REDACTED]"
    assert stored["idempotency_key"] == "keep-1"
    assert stored["nested"]["note"] == "Authorization=[REDACTED]"
    assert stored["nested"]["rows"] == [{"secret": "[REDACTED]", "count": 3}]
    assert audit.receipt(receipt["event_id"])["receipt_id"] == receipt["event_id"]
