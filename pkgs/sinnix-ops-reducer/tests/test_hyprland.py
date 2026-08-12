from sinnix_ops_reducer.hyprland import (
    HyprlandState,
    reconcile_activewindow,
    reduce_socket_event,
)


def test_socket_fixture_enters_and_clears_fullscreen_game() -> None:
    state = HyprlandState()
    assert reduce_socket_event(state, "fullscreen>>1", now=1)["fullscreen_game"] is True
    assert reduce_socket_event(state, "fullscreen>>2", now=2)["fullscreen_game"] is True
    assert (
        reduce_socket_event(state, "fullscreen>>0", now=3)["fullscreen_game"] is False
    )


def test_static_content_transition_is_rate_limited_and_unknown_bounded() -> None:
    state = HyprlandState()
    assert (
        reduce_socket_event(state, "activewindow>>mpv,title", now=10)["static_content"]
        is False
    )
    assert (
        reduce_socket_event(state, "activewindow>>mpv,title", now=71)["static_content"]
        is True
    )
    assert reduce_socket_event(state, "unknown>>x", now=72)["diagnostics"] == 1


def test_restart_reconciliation_restores_fullscreen_and_static_state() -> None:
    state = HyprlandState()
    snapshot = reconcile_activewindow(
        state, {"fullscreen": 2, "class": "mpv"}, now=100.0
    )

    assert snapshot == {
        "fullscreen_game": True,
        "static_content": True,
        "diagnostics": 0,
    }
    assert state.last_static_transition == 100.0
