import os

from sinnix_phone_dispatcher import state


def test_new_state_boundaries_are_private(isolated_state_dirs):
    previous = os.umask(0o022)
    try:
        state.ensure_dirs()
    finally:
        os.umask(previous)
    for path in (state.STATE_DIR, state.INBOX_DIR, state.RECEIPTS_DIR,
                 state.NOTIFY_DIR, state.DECKS_DIR, state.TOKENS_DIR):
        assert path.stat().st_mode & 0o777 == 0o700
