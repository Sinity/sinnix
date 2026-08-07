from sinnix_quota.normalize import compare, normalize_cost, normalize_usage, redact_json


def codex_fixture(remaining: float = 72.0) -> dict:
    return {
        "schemaVersion": "caut.v1",
        "generatedAt": "2026-08-07T00:00:00Z",
        "data": [
            {
                "provider": "codex",
                "account": "operator@example.invalid",
                "plan": "pro",
                "usage": {
                    "primary": {
                        "usedPercent": 28,
                        "remainingPercent": remaining,
                        "windowMinutes": 300,
                        "resetsAt": "2026-08-07T05:00:00Z",
                    }
                },
            }
        ],
    }


def test_codex_and_non_codex_normalize_without_identity_leak() -> None:
    codex = normalize_usage(codex_fixture(), "codexbar")
    claude = normalize_usage(
        {
            **codex_fixture(60),
            "data": [{**codex_fixture(60)["data"][0], "provider": "claude"}],
        },
        "caut",
    )
    assert codex[0]["schema"] == "sinnix-quota-v1"
    assert codex[0]["account_hash"].startswith("sha256:")
    assert "operator@example.invalid" not in str(codex)
    assert claude[0]["source"] == "caut"
    assert codex[0]["kind"] != "calculated_cost"


def test_plan_epoch_changes_and_disagreement_is_preserved() -> None:
    first = normalize_usage(codex_fixture(), "codexbar")
    changed = normalize_usage(
        {
            **codex_fixture(),
            "data": [{**codex_fixture()["data"][0], "plan": "team"}],
        },
        "codexbar",
    )
    canary = normalize_usage(codex_fixture(60), "caut")
    assert first[0]["plan_epoch"] != changed[0]["plan_epoch"]
    assert compare(first, canary)[0]["resolution"] == "preserved_separately"


def test_cost_is_separate_and_redaction_removes_secrets() -> None:
    cost = normalize_cost(
        {
            "data": [
                {
                    "provider": "codex",
                    "apiKey": "secret",
                    "totals": {"totalTokens": 12, "totalCost": 0.4},
                }
            ]
        },
        "ccusage",
    )
    assert cost[0]["kind"] == "calculated_cost"
    assert cost[0]["native_units"]["total_cost_usd"] == 0.4
    assert redact_json({"apiKey": "secret", "email": "user@example.invalid"}) == {
        "apiKey": "[redacted]",
        "email": "[redacted]",
    }


def test_codexbar_linux_json_array_derives_remaining_and_plan() -> None:
    rows = normalize_usage(
        [
            {
                "provider": "codex",
                "source": "oauth",
                "usage": {
                    "identity": {"accountEmail": "operator@example.invalid"},
                    "loginMethod": "pro",
                    "secondary": {
                        "usedPercent": 64,
                        "windowMinutes": 10080,
                        "resetsAt": "2026-08-11T20:34:18Z",
                    },
                },
            }
        ],
        "codexbar",
    )
    assert rows[0]["plan"] == "pro"
    assert rows[0]["window"]["remaining_fraction"] == 0.36
    assert rows[0]["account_hash"].startswith("sha256:")
