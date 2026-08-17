"""Every test runs against a tmp_path state tree, never the real
/realm/state/sinnix-phone -- state.py's dir constants are resolved once at
import time from SINNIX_PHONE_STATE_DIR/SINNIX_PHONE_LAKE, so tests that
exercise receipt/token writes patch them directly rather than relying on
those env vars (which a real dev shell may already have set)."""

from __future__ import annotations

import pytest

import sinnix_phone_dispatcher.dispatch as dispatch_mod
import sinnix_phone_dispatcher.execute as execute_mod
import sinnix_phone_dispatcher.state as state_mod


@pytest.fixture(autouse=True)
def isolated_state_dirs(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    lake_root = tmp_path / "lake"
    inbox_dir = state_dir / "inbox"
    receipts_dir = inbox_dir / "receipts"
    notify_dir = inbox_dir / "notify"
    decks_dir = inbox_dir / "decks"
    tokens_dir = state_dir / "tokens"

    monkeypatch.setattr(state_mod, "STATE_DIR", state_dir)
    monkeypatch.setattr(state_mod, "LAKE_ROOT", lake_root)
    monkeypatch.setattr(state_mod, "INBOX_DIR", inbox_dir)
    monkeypatch.setattr(state_mod, "RECEIPTS_DIR", receipts_dir)
    monkeypatch.setattr(state_mod, "NOTIFY_DIR", notify_dir)
    monkeypatch.setattr(state_mod, "DECKS_DIR", decks_dir)
    monkeypatch.setattr(state_mod, "TOKENS_DIR", tokens_dir)
    # execute.py imported TOKENS_DIR/LAKE_ROOT by name, a separate binding in
    # its own module namespace -- both must move together or seen_token/
    # mark_token/land_shared would still touch the real state tree.
    monkeypatch.setattr(execute_mod, "TOKENS_DIR", tokens_dir)
    monkeypatch.setattr(execute_mod, "LAKE_ROOT", lake_root)
    monkeypatch.setattr(dispatch_mod, "INBOX_DIR", inbox_dir)

    return {
        "state_dir": state_dir,
        "lake_root": lake_root,
        "inbox_dir": inbox_dir,
        "receipts_dir": receipts_dir,
        "notify_dir": notify_dir,
        "decks_dir": decks_dir,
        "tokens_dir": tokens_dir,
    }
