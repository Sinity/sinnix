"""The downward direction the phone now fetches instead of prime pushing:
listing with hashes, name validation, and what a confirmation consumes.

Mutations that would fail these:

* deleting a confirmed entry without comparing the sha256 to the file still
  present fails test_confirming_a_stale_sha_does_not_delete;
* treating decks (or the generated state files) as one-shots fails
  test_confirming_a_deck_keeps_it -- the shelf would lose an instrument the
  moment the phone read it;
* accepting a name outside the three known subdirectories fails
  test_traversal_names_are_refused.
"""

from __future__ import annotations

import hashlib
import json
import os
from http import HTTPStatus
from pathlib import Path

import pytest
import sinnix_phone_dispatcher.inbox as inbox_mod


@pytest.fixture(autouse=True)
def stub_generated(monkeypatch):
    """The two generated entries are built from live host state (the ops
    reducer's socket); this suite is about the inbox mechanics, so they are
    replaced by builders with no dependencies."""
    monkeypatch.setattr(
        inbox_mod,
        "GENERATED",
        {
            "glance.json": lambda: {"attention": []},
            "steering.json": lambda: {"ready": []},
        },
    )


def _write(isolated_state_dirs, sub: str, name: str, text: str) -> None:
    d = isolated_state_dirs["inbox_dir"] / sub
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(text, encoding="utf-8")


def test_listing_carries_a_sha_the_bytes_match(isolated_state_dirs) -> None:
    _write(isolated_state_dirs, "receipts", "r1.json", '{"title":"Scored"}\n')

    _, payload = inbox_mod.list_inbox()
    entry = next(f for f in payload["files"] if f["name"] == "receipts/r1.json")

    status, body = inbox_mod.read_inbox("receipts/r1.json")
    assert status == HTTPStatus.OK
    assert hashlib.sha256(body).hexdigest() == entry["sha256"]
    assert entry["one_shot"] is True


def test_generated_state_is_served_without_a_file(isolated_state_dirs) -> None:
    _, payload = inbox_mod.list_inbox()
    names = [f["name"] for f in payload["files"]]
    assert "glance.json" in names and "steering.json" in names

    status, body = inbox_mod.read_inbox("glance.json")
    assert status == HTTPStatus.OK
    assert json.loads(body) == {"attention": []}
    assert not (isolated_state_dirs["inbox_dir"] / "glance.json").exists()


def test_generated_hash_ignores_request_time(monkeypatch, isolated_state_dirs) -> None:
    calls = iter(["2026-08-27T10:00:00Z", "2026-08-27T10:01:00Z"])
    monkeypatch.setattr(
        inbox_mod,
        "GENERATED",
        {"glance.json": lambda: {"generated_at": next(calls), "attention": []}},
    )

    _, first = inbox_mod.list_inbox()
    _, second = inbox_mod.list_inbox()

    assert first["files"][0]["sha256"] == second["files"][0]["sha256"]


def test_a_half_written_receipt_is_not_offered(isolated_state_dirs) -> None:
    _write(isolated_state_dirs, "receipts", "r1.json.part", '{"title":"hal')

    _, payload = inbox_mod.list_inbox()

    assert [f for f in payload["files"] if f["name"].startswith("receipts/")] == []


def test_confirming_a_receipt_deletes_it(isolated_state_dirs) -> None:
    text = '{"title":"Scored"}\n'
    _write(isolated_state_dirs, "receipts", "r1.json", text)
    digest = hashlib.sha256(text.encode()).hexdigest()

    status, payload = inbox_mod.confirm_inbox("receipts/r1.json", digest)

    assert status == HTTPStatus.OK
    assert payload["deleted"] is True
    assert not (isolated_state_dirs["receipts_dir"] / "r1.json").exists()
    assert not list(isolated_state_dirs["inbox_dir"].glob(".confirmation-*.json"))


@pytest.mark.parametrize("publish_again", [False, True])
def test_confirmation_preserves_replacement_before_claim(
    isolated_state_dirs, monkeypatch, publish_again,
):
    original = b'{"title":"original"}\n'
    replacement = b'{"title":"replacement"}\n'
    latest = b'{"title":"latest"}\n'
    _write(isolated_state_dirs, "receipts", "r1.json", original.decode())
    path = isolated_state_dirs["receipts_dir"] / "r1.json"
    sha = inbox_mod._sha
    calls = 0

    def digest(body):
        nonlocal calls
        calls += 1
        if calls == 1 or (calls == 2 and publish_again):
            temporary = path.with_suffix(".next")
            temporary.write_bytes(replacement if calls == 1 else latest)
            temporary.replace(path)
        return sha(body)

    monkeypatch.setattr(inbox_mod, "_sha", digest)
    status, payload = inbox_mod.confirm_inbox("receipts/r1.json", sha(original))
    assert status == HTTPStatus.UNPROCESSABLE_ENTITY
    assert path.read_bytes() == (latest if publish_again else replacement)
    assert Path(payload["retained_at"]).read_bytes() == replacement
    assert payload["current_path_restored"] is not publish_again


def test_confirmation_keeps_new_publication_after_claim(isolated_state_dirs, monkeypatch):
    original = b'{"title":"original"}\n'
    replacement = b'{"title":"replacement"}\n'
    _write(isolated_state_dirs, "receipts", "r1.json", original.decode())
    path = isolated_state_dirs["receipts_dir"] / "r1.json"
    sha = inbox_mod._sha
    calls = 0

    def digest(body):
        nonlocal calls
        calls += 1
        if calls == 2:
            path.write_bytes(replacement)
        return sha(body)

    monkeypatch.setattr(inbox_mod, "_sha", digest)
    status, payload = inbox_mod.confirm_inbox("receipts/r1.json", sha(original))
    assert status == HTTPStatus.OK and payload["deleted"] is True
    assert path.read_bytes() == replacement
    assert not list(isolated_state_dirs["inbox_dir"].glob(".confirmation-*.json"))


def test_claim_read_failure_preserves_receipt(isolated_state_dirs, monkeypatch):
    text = '{"title":"retained"}\n'
    _write(isolated_state_dirs, "receipts", "r1.json", text)
    open_file = os.open

    def fail_claim(path, flags, *args, **kwargs):
        if Path(path).name.startswith(".confirmation-") and flags & os.O_NONBLOCK:
            raise OSError("synthetic claim read failure")
        return open_file(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", fail_claim)
    status, payload = inbox_mod.confirm_inbox(
        "receipts/r1.json", hashlib.sha256(text.encode()).hexdigest(),
    )
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert Path(payload["retained_at"]).read_bytes() == text.encode()
    assert (isolated_state_dirs["receipts_dir"] / "r1.json").read_bytes() == text.encode()


def test_nonregular_replacement_is_preserved_without_blocking(isolated_state_dirs, monkeypatch):
    text = '{"title":"original"}\n'
    _write(isolated_state_dirs, "receipts", "r1.json", text)
    path = isolated_state_dirs["receipts_dir"] / "r1.json"
    sha = inbox_mod._sha

    def replace_with_fifo(body):
        path.unlink()
        os.mkfifo(path)
        return sha(body)

    monkeypatch.setattr(inbox_mod, "_sha", replace_with_fifo)
    status, payload = inbox_mod.confirm_inbox("receipts/r1.json", sha(text.encode()))
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "not a regular file" in payload["detail"]
    assert Path(payload["retained_at"]).is_fifo() and path.is_fifo()


def test_interrupted_confirmation_retains_claimed_bytes(isolated_state_dirs, monkeypatch):
    text = '{"title":"retained"}\n'
    _write(isolated_state_dirs, "receipts", "r1.json", text)
    sha = inbox_mod._sha
    calls = 0

    def interrupt(body):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt
        return sha(body)

    monkeypatch.setattr(inbox_mod, "_sha", interrupt)
    with pytest.raises(KeyboardInterrupt):
        inbox_mod.confirm_inbox("receipts/r1.json", sha(text.encode()))
    claims = list(isolated_state_dirs["inbox_dir"].glob(".confirmation-*.json"))
    assert len(claims) == 1 and claims[0].read_bytes() == text.encode()


def test_ambiguous_rename_failure_never_removes_claimed_receipt(isolated_state_dirs, monkeypatch):
    text = '{"title":"retained"}\n'
    _write(isolated_state_dirs, "receipts", "r1.json", text)
    rename = os.rename

    def committed_then_failed(path, target, **kwargs):
        rename(path, target, **kwargs)
        raise OSError("synthetic ambiguous rename failure")

    monkeypatch.setattr(os, "rename", committed_then_failed)
    status, payload = inbox_mod.confirm_inbox(
        "receipts/r1.json", hashlib.sha256(text.encode()).hexdigest(),
    )
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert Path(payload["retained_at"]).read_bytes() == text.encode()
    assert (isolated_state_dirs["receipts_dir"] / "r1.json").read_bytes() == text.encode()


def test_reconfirming_a_gone_receipt_is_a_success(isolated_state_dirs) -> None:
    status, payload = inbox_mod.confirm_inbox("receipts/gone.json", "0" * 64)

    assert status == HTTPStatus.OK
    assert payload["already_gone"] is True


def test_confirming_a_stale_sha_does_not_delete(isolated_state_dirs) -> None:
    _write(isolated_state_dirs, "receipts", "r1.json", '{"title":"Scored"}\n')

    status, payload = inbox_mod.confirm_inbox("receipts/r1.json", "0" * 64)

    assert status == HTTPStatus.UNPROCESSABLE_ENTITY
    assert payload["ok"] is False
    assert (isolated_state_dirs["receipts_dir"] / "r1.json").is_file()


def test_confirming_a_deck_keeps_it(isolated_state_dirs) -> None:
    text = '{"engine":"reaction"}\n'
    _write(isolated_state_dirs, "decks", "pvt.json", text)

    status, payload = inbox_mod.confirm_inbox(
        "decks/pvt.json", hashlib.sha256(text.encode()).hexdigest()
    )

    assert status == HTTPStatus.OK
    assert payload["retained"] is True
    assert (isolated_state_dirs["decks_dir"] / "pvt.json").is_file()


@pytest.mark.parametrize(
    "name",
    [
        "../../etc/passwd",
        "receipts/../../escape",
        "tokens/abcd",
        "receipts/",
        "receipts/.hidden",
        "receipts/fixture.json\n",
    ],
)
def test_traversal_names_are_refused(name) -> None:
    assert inbox_mod.read_inbox(name)[0] == HTTPStatus.BAD_REQUEST
    assert inbox_mod.confirm_inbox(name, "0" * 64)[0] == HTTPStatus.BAD_REQUEST


def test_a_missing_entry_is_a_404(isolated_state_dirs) -> None:
    status, payload = inbox_mod.read_inbox("notify/nothing.json")
    assert status == HTTPStatus.NOT_FOUND
    assert payload["ok"] is False


@pytest.mark.parametrize("subdirectory_link", [False, True])
def test_symlinks_cannot_expose_outside_inbox(isolated_state_dirs, tmp_path, subdirectory_link):
    outside = tmp_path / 'outside'
    outside.mkdir()
    target = outside / 'entry.json'
    target.write_bytes(b'synthetic outside inbox')
    root = isolated_state_dirs['inbox_dir']
    root.mkdir(parents=True)
    if subdirectory_link:
        (root / 'receipts').symlink_to(outside, target_is_directory=True)
    else:
        (root / 'receipts').mkdir()
        (root / 'receipts' / 'entry.json').symlink_to(target)
    before = target.stat()
    status, body = inbox_mod.read_inbox('receipts/entry.json')
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert isinstance(body, dict) and not body['ok']
    listing_status, listing = inbox_mod.list_inbox()
    assert listing_status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert not listing['ok'] and 'files' not in listing
    status, body = inbox_mod.confirm_inbox('receipts/entry.json', hashlib.sha256(target.read_bytes()).hexdigest())
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR
    after = target.stat()
    assert (after.st_ino, after.st_size, after.st_mtime_ns) == (before.st_ino, before.st_size, before.st_mtime_ns)
    assert target.read_bytes() == b'synthetic outside inbox'
    assert (root / 'receipts' / 'entry.json').exists()


@pytest.mark.parametrize("kind", ["directory", "fifo"])
def test_wrong_type_is_unavailable_not_already_consumed(isolated_state_dirs, kind):
    root = isolated_state_dirs['receipts_dir']
    root.mkdir(parents=True)
    path = root / 'entry.json'
    if kind == 'directory':
        path.mkdir()
    else:
        os.mkfifo(path)
    for status, body in [inbox_mod.read_inbox('receipts/entry.json'),
                         inbox_mod.confirm_inbox('receipts/entry.json', '0' * 64)]:
        assert status == HTTPStatus.INTERNAL_SERVER_ERROR
        assert not body['ok'] and not body.get('already_gone')
    assert path.is_dir() if kind == 'directory' else path.is_fifo()


def test_refused_entry_reads_do_not_leak_descriptors(isolated_state_dirs):
    root = isolated_state_dirs['receipts_dir']
    root.mkdir(parents=True)
    path = root / 'entry.json'
    path.mkdir()
    before = set(os.listdir('/proc/self/fd'))
    for _ in range(8):
        assert inbox_mod.read_inbox('receipts/entry.json')[0] == HTTPStatus.INTERNAL_SERVER_ERROR
    assert set(os.listdir('/proc/self/fd')) == before


@pytest.mark.parametrize("denied_at", ["root", "directory", "entry", "enumeration"])
def test_listing_access_errors_are_not_empty_inboxes(isolated_state_dirs, monkeypatch, denied_at):
    _write(isolated_state_dirs, 'receipts', 'entry.json', '{}')
    original_open = os.open
    original_listdir = os.listdir
    def guarded_open(path, *args, **kwargs):
        target = str(path)
        if ((denied_at == 'root' and target == str(isolated_state_dirs['inbox_dir'])) or
            (denied_at == 'directory' and target == 'receipts') or
            (denied_at == 'entry' and target == 'entry.json')):
            raise PermissionError('synthetic denied inbox')
        return original_open(path, *args, **kwargs)
    def guarded_listdir(path):
        if denied_at == 'enumeration' and isinstance(path, int):
            raise PermissionError('synthetic denied inbox')
        return original_listdir(path)
    before = set(os.listdir('/proc/self/fd'))
    monkeypatch.setattr(os, 'open', guarded_open)
    monkeypatch.setattr(os, 'listdir', guarded_listdir)
    status, payload = inbox_mod.list_inbox()
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert not payload['ok'] and 'files' not in payload
    assert 'synthetic denied inbox' in payload['detail']
    assert set(os.listdir('/proc/self/fd')) == before


def test_missing_inbox_is_empty_but_wrong_type_is_unavailable(isolated_state_dirs):
    inbox_mod.GENERATED.clear()
    assert inbox_mod.list_inbox()[1]['files'] == []
    root = isolated_state_dirs['inbox_dir']
    root.parent.mkdir(parents=True)
    root.write_bytes(b'synthetic wrong object')
    status, payload = inbox_mod.list_inbox()
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR and not payload['ok']
    assert root.read_bytes() == b'synthetic wrong object'


def test_listing_handles_concurrently_consumed_receipt(isolated_state_dirs, monkeypatch):
    _write(isolated_state_dirs, 'receipts', 'entry.json', '{}')
    original = inbox_mod._read_regular
    def consumed(path, **kwargs):
        if path == 'entry.json':
            raise FileNotFoundError('synthetic concurrent confirmation')
        return original(path, **kwargs)
    monkeypatch.setattr(inbox_mod, '_read_regular', consumed)
    status, payload = inbox_mod.list_inbox()
    assert status == HTTPStatus.OK and payload['ok']
    assert not any(f['name'] == 'receipts/entry.json' for f in payload['files'])


@pytest.mark.parametrize("replace_root", [False, True])
@pytest.mark.parametrize("after_claim", [False, True])
def test_confirmation_stays_with_opened_directories(isolated_state_dirs, tmp_path, monkeypatch,
                                                     replace_root, after_claim):
    content = b'synthetic same bytes'
    _write(isolated_state_dirs, 'receipts', 'entry.json', content.decode())
    root = isolated_state_dirs['inbox_dir']
    original = root if replace_root else root / 'receipts'
    retained = tmp_path / 'retained-original'
    outside = tmp_path / 'outside'
    outside.mkdir()
    external_parent = outside / 'receipts' if replace_root else outside
    external_parent.mkdir(exist_ok=True)
    external_file = external_parent / 'entry.json'
    external_file.write_bytes(content)
    before = external_file.stat()
    sha = inbox_mod._sha
    calls = 0
    def digest(body):
        nonlocal calls
        calls += 1
        if calls == (2 if after_claim else 1):
            original.rename(retained)
            original.symlink_to(outside, target_is_directory=True)
        return sha(body)
    monkeypatch.setattr(inbox_mod, '_sha', digest)
    status, payload = inbox_mod.confirm_inbox('receipts/entry.json', sha(content))
    assert status == HTTPStatus.OK and payload['deleted']
    after = external_file.stat()
    assert (after.st_ino, after.st_size, after.st_mtime_ns) == (before.st_ino, before.st_size, before.st_mtime_ns)
    assert external_file.read_bytes() == content
    retained_entry = retained / 'receipts' / 'entry.json' if replace_root else retained / 'entry.json'
    assert not retained_entry.exists()
    assert not list(retained.rglob('.confirmation-*.json'))


def test_claim_recovery_reports_relocated_root(isolated_state_dirs, tmp_path, monkeypatch):
    _write(isolated_state_dirs, 'receipts', 'entry.json', 'original')
    root = isolated_state_dirs['inbox_dir']
    retained = tmp_path / 'retained-inbox'
    outside = tmp_path / 'outside'
    outside.mkdir()
    sha = inbox_mod._sha
    calls = 0
    def digest(body):
        nonlocal calls
        calls += 1
        if calls == 1:
            (root / 'receipts' / 'entry.json').write_text('replacement')
            root.rename(retained)
            root.symlink_to(outside, target_is_directory=True)
        return sha(body)
    monkeypatch.setattr(inbox_mod, '_sha', digest)
    status, payload = inbox_mod.confirm_inbox('receipts/entry.json', sha(b'original'))
    assert status == HTTPStatus.UNPROCESSABLE_ENTITY
    claim = Path(payload['retained_at'])
    assert claim.parent == retained and claim.read_bytes() == b'replacement'
    assert (retained / 'receipts' / 'entry.json').read_bytes() == b'replacement'
    assert payload['current_path_restored']
    assert list(outside.iterdir()) == []


def test_atomic_temporary_is_not_offered_before_publication(isolated_state_dirs):
    root = isolated_state_dirs['receipts_dir']
    root.mkdir(parents=True)
    temporary = root / '.fixture.json.atomic-tmp-test'
    temporary.write_bytes(b'{"incomplete":')
    status, payload = inbox_mod.list_inbox()
    assert status == HTTPStatus.OK and payload['ok']
    assert not any(f['name'].startswith('receipts/') for f in payload['files'])
    assert temporary.read_bytes() == b'{"incomplete":'
    completed = b'{"fixture":"complete"}\n'
    temporary.write_bytes(completed)
    temporary.rename(root / 'fixture.json')
    status, payload = inbox_mod.list_inbox()
    row = next(f for f in payload['files'] if f['name'] == 'receipts/fixture.json')
    assert status == HTTPStatus.OK and row['sha256'] == hashlib.sha256(completed).hexdigest()
    assert inbox_mod.read_inbox('receipts/fixture.json') == (HTTPStatus.OK, completed)
