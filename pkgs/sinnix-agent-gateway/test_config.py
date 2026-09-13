from pathlib import Path

from sinnix_agent_gateway.config import GatewayConfig


def test_command_defaults_and_explicit_overrides(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"stateDir": "' + str(tmp_path / "state") + '"}')
    defaults = GatewayConfig.load(path)
    assert (defaults.systemctl_command, defaults.observe_command, defaults.beads_command) == ("systemctl", "sinnix-observe", "bd")
    path.write_text('{"stateDir": "' + str(tmp_path / "state") + '", "systemctlCommand": "custom-systemctl"}')
    assert GatewayConfig.load(path).systemctl_command == "custom-systemctl"
