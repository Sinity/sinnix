"""Page input failures and manager-qualified unit observations."""

import json
from html.parser import HTMLParser

from sinnix_ops_reducer.pages import probes, services


def test_invalid_utf8_json_is_an_explicit_input_error(tmp_path):
    path = tmp_path / "source.json"
    path.write_bytes(b"\xff")
    value, error = probes.load_json(path)
    assert value is None
    assert str(path) in error and "not valid JSON" in error
    assert path.read_bytes() == b"\xff"
    path.write_text('{"label": "zażółć"}', encoding="utf-8")
    assert probes.load_json(path) == ({"label": "zażółć"}, None)


def observed(manager, units, properties):
    assert units == ["shared.service"]
    return {
        "shared.service": {
            "LoadState": "loaded",
            "ActiveState": "active" if manager == "system" else "inactive",
            "SubState": "running" if manager == "system" else "dead",
            "InvocationID": manager + "-instance",
            "UnitFileState": "enabled",
        }
    }


def test_same_named_units_retain_both_managers(monkeypatch):
    monkeypatch.setattr(probes, "show_units", observed)
    states = probes.unit_states(
        [("system", "shared.service"), ("user", "shared.service")]
    )
    assert len(states) == 2
    assert states["system", "shared.service"]["ActiveState"] == "active"
    assert states["user", "shared.service"]["ActiveState"] == "inactive"


class Targets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []

    def handle_starttag(self, tag, attrs):
        value = dict(attrs).get("data-expected-target")
        if value and value != "null":
            self.targets.append(json.loads(value))


def assert_targets(html):
    parser = Targets()
    parser.feed(html)
    assert len(parser.targets) == 3  # system stop/restart and user start.
    for target in parser.targets:
        manager = target["manager"]
        assert target["properties"]["InvocationID"] == manager + "-instance"
        assert target["properties"]["ActiveState"] == (
            "active" if manager == "system" else "inactive"
        )
    assert {target["manager"] for target in parser.targets} == {"system", "user"}


def test_services_controls_keep_their_manager_observation(monkeypatch):
    monkeypatch.setattr(probes, "show_units", observed)
    inventory = {
        "surfaces": {
            manager: {
                "unit": "shared.service",
                "manager": manager,
                "observe": {"restartable": True},
            }
            for manager in ("system", "user")
        }
    }
    assert_targets(services.render_services({}, inventory, "2026-01-01T00:00:00Z"))
