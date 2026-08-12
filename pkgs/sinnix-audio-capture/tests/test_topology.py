from __future__ import annotations

from sinnix_audio_capture.topology import event_payload, parse_pw_mon_stream

_ADDED_NODE = """\
added:
\tid: 49
\tpermissions: rwxm-
\ttype: PipeWire:Interface:Node (version 3)
\tproperties:
\t\tfactory.name = "api.alsa.seq.bridge"
\t\tnode.name = "Midi-Bridge"
\t\tmedia.class = "Midi/Bridge"
\t\tobject.id = "49"

"""

_ADDED_LINK = """\
added:
\tid: 93
\tpermissions: r-x--
\ttype: PipeWire:Interface:Link (version 3)
\toutput-node-id: 60
\toutput-port-id: 55
\tinput-node-id: 83
\tinput-port-id: 81

"""

_ADDED_SKIPPED = """\
added:
\tid: 12
\ttype: PipeWire:Interface:Core (version 4)

"""

_REMOVED_NODE = """\
removed:
\tid: 49

"""


def _lines(*blocks: str) -> list[str]:
    text = "".join(blocks)
    return text.splitlines(keepends=True)


def test_parse_added_node_event():
    events = list(parse_pw_mon_stream(_lines(_ADDED_NODE)))
    assert len(events) == 1
    event = events[0]
    assert event.action == "added"
    assert event.id == 49
    assert event.kind == "node"
    assert event.summary == {"node.name": "Midi-Bridge", "media.class": "Midi/Bridge"}


def test_parse_added_link_event_captures_endpoint_fields():
    events = list(parse_pw_mon_stream(_lines(_ADDED_LINK)))
    assert len(events) == 1
    event = events[0]
    assert event.kind == "link"
    assert event.summary == {
        "output-node-id": "60",
        "output-port-id": "55",
        "input-node-id": "83",
        "input-port-id": "81",
    }


def test_non_node_port_link_types_are_skipped():
    events = list(parse_pw_mon_stream(_lines(_ADDED_SKIPPED)))
    assert events == []


def test_removed_event_uses_id_kind_cache():
    cache: dict[int, str] = {}
    added = list(parse_pw_mon_stream(_lines(_ADDED_NODE), id_kind_cache=cache))
    assert added[0].kind == "node"
    assert cache == {49: "node"}

    removed = list(parse_pw_mon_stream(_lines(_REMOVED_NODE), id_kind_cache=cache))
    assert len(removed) == 1
    assert removed[0].action == "removed"
    assert removed[0].kind == "node"
    assert 49 not in cache


def test_removed_event_for_id_not_in_cache_is_dropped():
    events = list(parse_pw_mon_stream(_lines(_REMOVED_NODE)))
    assert events == []  # no cache entry (predates this process) -> dropped, see module docstring


def test_event_payload_shape():
    events = list(parse_pw_mon_stream(_lines(_ADDED_NODE)))
    payload = event_payload(events[0])
    assert payload == {
        "action": "added",
        "kind": "node",
        "id": 49,
        "node.name": "Midi-Bridge",
        "media.class": "Midi/Bridge",
    }
