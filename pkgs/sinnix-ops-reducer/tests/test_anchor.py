from datetime import datetime, timedelta, timezone

from sinnix_ops_reducer.anchor import expire_anchor, reduce_anchor_event
from sinnix_ops_reducer.reducer import Reducer
import json


def test_long_afk_produces_reference_only_anchor_and_deduplicates() -> None:
    now = datetime(2026, 8, 7, 12, tzinfo=timezone.utc)
    event = {"started_at": "2026-08-07T11:00:00Z", "resumed_at": "2026-08-07T12:00:00Z", "observe": {"focused_project": "sinnix", "recent_commits": ["git:abc"], "polylogue": None}}
    anchor = reduce_anchor_event(event, now)
    assert anchor["brief"]["focused_project"] == "sinnix"
    assert anchor["brief"]["recent_commits"] == ["git:abc"]
    assert "transcript" not in str(anchor)
    assert reduce_anchor_event(event, now, previous=anchor) == anchor


def test_short_afk_is_ignored_and_anchor_expires() -> None:
    now = datetime(2026, 8, 7, 12, tzinfo=timezone.utc)
    assert reduce_anchor_event({"started_at": "2026-08-07T11:40:00Z", "resumed_at": "2026-08-07T12:00:00Z"}, now) is None
    anchor = reduce_anchor_event({"started_at": "2026-08-07T11:00:00Z", "resumed_at": "2026-08-07T12:00:00Z"}, now)
    assert expire_anchor(anchor, datetime(2026, 8, 7, 13, 1, tzinfo=timezone.utc)) is None


def test_reducer_consumes_resume_event_once(tmp_path) -> None:
    resumed_at = datetime.now(timezone.utc).replace(microsecond=0)
    started_at = resumed_at - timedelta(hours=1)
    event_path = tmp_path / "resume.json"
    event_path.write_text(json.dumps({"started_at": started_at.isoformat(), "resumed_at": resumed_at.isoformat()}))
    reducer = Reducer(tmp_path / "snapshot.json", tmp_path / "token", lambda: {"schema": "observe"})
    reducer.anchor_event_path = event_path
    snapshot = reducer.refresh()
    assert snapshot["state"]["session_anchor"]["schema"] == "sinnix-session-anchor-v1"
    assert not event_path.exists()
