from __future__ import annotations

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
