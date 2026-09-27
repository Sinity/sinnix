import json
from pathlib import Path

import pytest
from sinnix_agent_gateway.config import GatewayConfig


def test_command_defaults_and_explicit_overrides(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"stateDir": "' + str(tmp_path / "state") + '"}')
    defaults = GatewayConfig.load(path)
    assert (
        defaults.systemctl_command,
        defaults.observe_command,
        defaults.beads_command,
    ) == ("systemctl", "sinnix-observe", "bd")
    assert str(defaults.runtime_inventory) == "/etc/sinnix/runtime-inventory.json"
    assert str(defaults.capability_index) == "/etc/sinnix/capability-index.json"
    path.write_text(
        '{"stateDir": "'
        + str(tmp_path / "state")
        + '", "systemctlCommand": "custom-systemctl"}'
    )
    assert GatewayConfig.load(path).systemctl_command == "custom-systemctl"


def test_project_default_checkout_is_an_explicit_absolute_path(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "gateway.json"
    store = tmp_path / "repository.git"
    linked = tmp_path / "linked"
    config_path.write_text(
        json.dumps(
            {
                "projects": {
                    "fixture": {
                        "path": str(store),
                        "defaultRef": "refs/heads/main",
                        "defaultCheckout": str(linked),
                    }
                }
            }
        )
    )
    project = GatewayConfig.load(config_path).projects["fixture"]
    assert project.path == store.resolve()
    assert project.default_ref == "refs/heads/main"
    assert project.default_checkout == linked.resolve()

    config_path.write_text(
        json.dumps(
            {"projects": {"fixture": {"path": str(store), "defaultCheckout": "linked"}}}
        )
    )
    with pytest.raises(ValueError, match="defaultCheckout must be an absolute path"):
        GatewayConfig.load(config_path)
