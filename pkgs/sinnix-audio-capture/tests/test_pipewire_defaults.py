from __future__ import annotations

from sinnix_audio_capture.pipewire_defaults import (
    DefaultTargets,
    parse_default_line,
    resolve_target,
)


def test_parse_default_line_sink():
    line = (
        "update: id:0 key:'default.audio.sink' "
        "value:'{\"name\":\"bluez_output.AC_80_0A_D4_08_48.1\"}' type:'Spa:String:JSON'\n"
    )
    kind, name = parse_default_line(line)
    assert kind == "sink"
    assert name == "bluez_output.AC_80_0A_D4_08_48.1"


def test_parse_default_line_source():
    line = (
        "update: id:0 key:'default.audio.source' "
        'value:\'{"name":"alsa_input.usb-FiiO_DigiHug_USB_Audio-01.analog-stereo"}\' '
        "type:'Spa:String:JSON'\n"
    )
    kind, name = parse_default_line(line)
    assert kind == "source"
    assert name == "alsa_input.usb-FiiO_DigiHug_USB_Audio-01.analog-stereo"


def test_parse_default_line_ignores_untracked_keys():
    line = "update: id:0 key:'default.configured.audio.sink' value:'{}' type:'Spa:String:JSON'\n"
    assert parse_default_line(line) is None


def test_parse_default_line_ignores_non_update_lines():
    assert parse_default_line("something else entirely\n") is None


def test_parse_default_line_null_value():
    line = "update: id:0 key:'default.audio.sink' value:'null' type:'Spa:String:JSON'\n"
    kind, name = parse_default_line(line)
    assert kind == "sink"
    assert name is None


def test_default_targets_apply_reports_change():
    targets = DefaultTargets()
    assert targets.apply("sink", "a") is True
    assert targets.apply("sink", "a") is False
    assert targets.apply("sink", "b") is True
    assert targets.sink == "b"


def test_resolve_target_mic_uses_source():
    targets = DefaultTargets(source="alsa_input.foo")
    assert resolve_target("mic", targets) == "alsa_input.foo"


def test_resolve_target_sink_monitor_appends_monitor_suffix():
    targets = DefaultTargets(sink="bluez_output.foo")
    assert resolve_target("sink-monitor", targets) == "bluez_output.foo.monitor"


def test_resolve_target_sink_monitor_none_when_unknown():
    targets = DefaultTargets()
    assert resolve_target("sink-monitor", targets) is None
