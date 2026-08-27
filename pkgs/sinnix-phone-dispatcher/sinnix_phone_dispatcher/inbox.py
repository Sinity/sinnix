"""What prime has for the phone, served for the phone to come and take.

This direction used to be the drain's other half: prime rsync'd
`/realm/state/sinnix-phone/inbox/` onto the device every thirty minutes, from
a host that had to be able to open an ssh session into Termux to do it. That
made receipts and decks depend on the phone being reachable FROM prime, which
is the harder of the two directions -- the phone roams, sleeps, and sits
behind carrier NAT, while prime is a fixed tailnet address that answers.

So the direction inverted and the durability moved with it. Prime writes and
waits; the app fetches on its own cadence, verifies the sha it was given, and
confirms what it landed. Three routes:

  * `GET /inbox` -- what is here, with a sha256 each, so the app can tell an
    unchanged file from one it has not seen;
  * `GET /inbox/file?name=` -- the bytes;
  * `POST /inbox/confirm?name=&sha256=` -- "landed", which deletes the
    one-shots.

Confirmation deletes receipts and notifications and does NOT delete glance,
steering or decks, exactly matching what the drain's two rsync invocations
did (`--remove-source-files` for the first pair, a plain copy for the rest).
A receipt is handed over; a deck is published.

`glance.json` and `steering.json` are not files here at all any more -- they
are built when asked for, from the same builders the live routes use. They
were only ever files because a drain had to have something to copy, and a
snapshot written half an hour before it is read is a snapshot with a
staleness problem that nothing downstream can see.
"""

from __future__ import annotations

import hashlib
import json
import re
from http import HTTPStatus
from pathlib import Path

from sinnix_lib.ledger import utc_ts

from .glance import build_glance, build_steering
from .state import INBOX_DIR

#: Generated on demand rather than read from disk, keyed to their builder.
GENERATED = {
    "glance.json": build_glance,
    "steering.json": build_steering,
}

#: Directories under the inbox, and whether a confirmed fetch consumes them.
#: One-shots are handed over -- prime must forget a receipt the phone holds,
#: or it is re-delivered on every fetch forever, and the app deletes each one
#: as it renders it. Decks are published state: the shelf reads them for as
#: long as they are meant to be offered.
SUBDIRS = {
    "receipts": True,
    "notify": True,
    "decks": False,
}

#: `receipts/20260818T041500Z-ab12cd34.json`, and nothing with a separator,
#: a dot-segment, or an unlisted parent. The phone names the file it wants,
#: so the check has to be an allowlist of shapes rather than a traversal
#: filter -- a client that can name any path can read anything this service
#: can read.
_NAME_RE = re.compile(r"^(receipts|notify|decks)/[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _resolve(name: str) -> Path | None:
    if not _NAME_RE.match(name):
        return None
    return INBOX_DIR / name


def _sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _generated_bytes(name: str) -> bytes:
    payload = GENERATED[name]().copy()
    # The fetch itself proves freshness. Including a request-time timestamp in
    # the persisted body changes its hash on every poll and makes the phone
    # download and rewrite otherwise identical state forever.
    payload.pop("generated_at", None)
    return (json.dumps(payload, indent=2) + "\n").encode("utf-8")


def list_inbox() -> tuple[HTTPStatus, dict]:
    """Everything waiting, with a hash each and whether fetching consumes it.

    The hash is what lets the app skip work: glance and steering are rebuilt
    on every request and usually differ, while a deck that has not changed
    since the last fetch is a download that does not need to happen.
    """
    files: list[dict] = []
    for name in GENERATED:
        body = _generated_bytes(name)
        files.append(
            {
                "name": name,
                "bytes": len(body),
                "sha256": _sha(body),
                "generated": True,
                "one_shot": False,
            }
        )
    for sub, one_shot in SUBDIRS.items():
        directory = INBOX_DIR / sub
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            # `.part` is a file prime is still writing (emit_receipt renames
            # into place); handing one over would be the same torn-read bug
            # the phone's own writers take care to avoid.
            if not path.is_file() or path.name.endswith(".part"):
                continue
            try:
                body = path.read_bytes()
            except OSError:
                continue
            files.append(
                {
                    "name": f"{sub}/{path.name}",
                    "bytes": len(body),
                    "sha256": _sha(body),
                    "generated": False,
                    "one_shot": one_shot,
                }
            )
    return HTTPStatus.OK, {"ok": True, "at": utc_ts(), "files": files}


def read_inbox(name: str) -> tuple[HTTPStatus, bytes | dict]:
    """The bytes of one inbox entry, or a JSON refusal."""
    if name in GENERATED:
        return HTTPStatus.OK, _generated_bytes(name)
    path = _resolve(name)
    if path is None:
        return HTTPStatus.BAD_REQUEST, {
            "ok": False,
            "detail": "unacceptable inbox name",
        }
    if not path.is_file():
        return HTTPStatus.NOT_FOUND, {"ok": False, "detail": f"no inbox entry {name!r}"}
    try:
        return HTTPStatus.OK, path.read_bytes()
    except OSError as exc:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "detail": str(exc)}


def confirm_inbox(name: str, declared_sha: str | None) -> tuple[HTTPStatus, dict]:
    """The phone has it. Forget the one-shots; keep the state.

    The sha is required for a delete and is checked against the file that is
    still here: a confirmation quoting a hash prime cannot reproduce is a
    confirmation of something else -- a receipt rewritten since the fetch, or
    a truncated download the app believed -- and deleting on it would destroy
    the copy that was never delivered.
    """
    if name in GENERATED:
        # Nothing to consume: the next request builds it again. Answered ok so
        # the app can confirm everything it fetched without special-casing.
        return HTTPStatus.OK, {
            "ok": True,
            "name": name,
            "retained": True,
            "generated": True,
        }
    path = _resolve(name)
    if path is None:
        return HTTPStatus.BAD_REQUEST, {
            "ok": False,
            "detail": "unacceptable inbox name",
        }
    sub = name.split("/", 1)[0]
    if not SUBDIRS.get(sub, False):
        return HTTPStatus.OK, {"ok": True, "name": name, "retained": True}
    if not path.is_file():
        # Already gone: a re-confirmed one-shot is a success, for the same
        # reason a re-uploaded chunk is. The phone retries a confirmation
        # whose answer it never saw.
        return HTTPStatus.OK, {
            "ok": True,
            "name": name,
            "deleted": False,
            "already_gone": True,
        }
    try:
        body = path.read_bytes()
    except OSError as exc:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "detail": str(exc)}
    digest = _sha(body)
    if not declared_sha or declared_sha.lower() != digest:
        return HTTPStatus.UNPROCESSABLE_ENTITY, {
            "ok": False,
            "detail": "sha256 does not match the file still here; not deleting",
            "expected": digest,
            "received": (declared_sha or "").lower(),
        }
    path.unlink(missing_ok=True)
    return HTTPStatus.OK, {"ok": True, "name": name, "deleted": True, "at": utc_ts()}
