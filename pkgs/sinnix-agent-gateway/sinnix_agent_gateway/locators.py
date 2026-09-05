"""Natural locators in, canonical refs out.

Every action that targets a resource accepts either its canonical
``sinnix://`` ref or the locator a person would naturally give (a path, a
window title, a unit name). Resolution yields exactly one ref; zero matches
fail ``not_found``; several matches fail ``conflict`` with the candidates so
the caller can retry with a ref. Effectful actions never guess.
"""

from __future__ import annotations

import base64
import binascii
import re
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote, unquote

from pydantic import Field, model_validator

from .results import ProtocolError
from .schemas import GatewayModel

FILE_REF_PREFIX = "sinnix://files/"


class Candidate(GatewayModel):
    ref: str
    label: str
    detail: dict[str, Any] = Field(default_factory=dict)


def ambiguous(kind: str, candidates: list[Candidate]) -> ProtocolError:
    return ProtocolError(
        "conflict",
        f"{kind} locator matches {len(candidates)} resources; pass one candidate ref",
        details={
            "kind": kind,
            "candidates": [candidate.model_dump() for candidate in candidates[:20]],
        },
    )


def not_found(kind: str, locator: Any) -> ProtocolError:
    return ProtocolError(
        "not_found",
        f"no {kind} matches the locator",
        details={"kind": kind, "locator": locator},
    )


def encode_file_ref(path: str) -> str:
    token = base64.urlsafe_b64encode(path.encode()).decode().rstrip("=")
    return f"{FILE_REF_PREFIX}{token}"


def decode_file_ref(ref: str) -> str:
    if not ref.startswith(FILE_REF_PREFIX):
        raise ProtocolError("invalid_request", "ref is not a host file ref")
    token = ref[len(FILE_REF_PREFIX) :]
    try:
        padded = token + "=" * (-len(token) % 4)
        path = base64.b64decode(padded.encode(), altchars=b"-_", validate=True).decode(
            "utf-8"
        )
    except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
        raise ProtocolError("invalid_request", "file reference is malformed") from exc
    if not path or len(path) > 4_096 or not path.startswith("/"):
        raise ProtocolError("invalid_request", "file reference is malformed")
    return path


class FileLocator(GatewayModel):
    """A host file or directory by absolute path or canonical ref."""

    path: str | None = Field(
        default=None,
        min_length=1,
        max_length=4_096,
        description="Absolute host path; ~ expands to the gateway user's home.",
    )
    ref: str | None = Field(
        default=None,
        pattern=r"^sinnix://files/[A-Za-z0-9_-]{1,8192}$",
        description="Canonical host-file ref returned by an earlier call.",
    )

    @model_validator(mode="after")
    def exactly_one(self) -> FileLocator:
        if (self.path is None) == (self.ref is None):
            raise ValueError("give exactly one of path or ref")
        return self

    def resolve(self) -> tuple[str, str]:
        """Return ``(absolute_path, canonical_ref)`` without touching the disk."""
        if self.ref is not None:
            path = decode_file_ref(self.ref)
            return path, self.ref
        raw = Path(self.path or "").expanduser()
        if not raw.is_absolute():
            raw = Path.home() / raw
        path = str(raw)
        return path, encode_file_ref(path)


# ------------------------------------------------------------ projects, beads

PROJECT_REF = re.compile(r"^sinnix://projects/([^/]+)$")
CHECKOUT_REF = re.compile(r"^sinnix://projects/([^/]+)/checkouts/([^/]+)$")
BEAD_REF = re.compile(r"^sinnix://projects/([^/]+)/beads/([^/]+)$")


def project_ref(project_id: str) -> str:
    return f"sinnix://projects/{quote(project_id, safe='')}"


def checkout_ref(project_id: str, checkout_id: str) -> str:
    return f"{project_ref(project_id)}/checkouts/{quote(checkout_id, safe='')}"


def bead_ref(project_id: str, bead_id: str) -> str:
    return f"{project_ref(project_id)}/beads/{quote(bead_id, safe='')}"


def _configured_project(runtime: Any, project_id: str) -> str:
    if project_id not in runtime.config.projects:
        raise not_found("project", project_id)
    return project_id


def _checkout_by_path(runtime: Any, raw: str) -> tuple[str, str]:
    """The deepest configured project checkout containing an absolute path."""
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise ProtocolError("invalid_request", "project path must be absolute")
    try:
        path = path.resolve()
    except OSError as exc:
        raise ProtocolError("invalid_request", "project path is unreadable") from exc
    best: tuple[int, str, str] | None = None
    for project in runtime.config.projects.values():
        try:
            root = project.path.resolve()
        except OSError:
            continue
        if path != root and root not in path.parents:
            continue
        depth = len(root.parts)
        if best is None or depth > best[0]:
            best = (depth, project.project_id, "default")
    if best is not None:
        return best[1], best[2]
    from .projects import ProjectError

    for project in runtime.config.projects.values():
        try:
            rows = runtime.projects.checkouts(project.project_id)["checkouts"]
        except (ProjectError, ProtocolError):
            continue
        for row in rows:
            root = Path(row["path"])
            if path == root or root in path.parents:
                return project.project_id, row["checkout_id"]
    raise not_found("checkout", raw)


class ProjectLocator(GatewayModel):
    """A configured project by canonical ref, project id, or a path inside it."""

    ref: str | None = Field(
        default=None,
        pattern=r"^sinnix://projects/[^/]+(?:/checkouts/[^/]+)?$",
        description="Canonical project or checkout ref.",
    )
    project: str | None = Field(
        default=None, min_length=1, max_length=128, description="Project id."
    )
    path: str | None = Field(
        default=None,
        min_length=1,
        max_length=4_096,
        description="Absolute host path inside a project checkout.",
    )

    @model_validator(mode="after")
    def exactly_one(self) -> ProjectLocator:
        if sum(value is not None for value in (self.ref, self.project, self.path)) != 1:
            raise ValueError("give exactly one of ref, project or path")
        return self

    def resolve(self, runtime: Any) -> str:
        """Return the project id; the project must be configured."""
        if self.ref is not None:
            match = PROJECT_REF.match(self.ref) or CHECKOUT_REF.match(self.ref)
            assert match is not None
            return _configured_project(runtime, unquote(match.group(1)))
        if self.project is not None:
            return _configured_project(runtime, self.project)
        return _checkout_by_path(runtime, self.path or "")[0]


class ResolvedCheckout(GatewayModel):
    project_id: str
    checkout_id: str | None = Field(
        description="None when the caller did not select a checkout (the configured root)."
    )
    ref: str
    project_ref: str
    checkout_ref: str


class CheckoutLocator(GatewayModel):
    """A project checkout by ref, project id (+ optional checkout id), or path."""

    ref: str | None = Field(
        default=None,
        pattern=r"^sinnix://projects/[^/]+(?:/checkouts/[^/]+)?$",
        description="Project ref (default checkout) or checkout ref.",
    )
    project: str | None = Field(default=None, min_length=1, max_length=128)
    checkout: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Checkout id from projects.get; omitted means the configured root.",
    )
    path: str | None = Field(
        default=None,
        min_length=1,
        max_length=4_096,
        description="Absolute host path inside a checkout (root or linked worktree).",
    )

    @model_validator(mode="after")
    def exactly_one(self) -> CheckoutLocator:
        if sum(value is not None for value in (self.ref, self.project, self.path)) != 1:
            raise ValueError("give exactly one of ref, project or path")
        if self.checkout is not None and self.project is None:
            raise ValueError("checkout requires project")
        return self

    def resolve(self, runtime: Any) -> ResolvedCheckout:
        checkout: str | None = self.checkout
        if self.ref is not None:
            match = CHECKOUT_REF.match(self.ref)
            if match is not None:
                project_id, checkout = unquote(match.group(1)), unquote(match.group(2))
            else:
                project_id = unquote(PROJECT_REF.match(self.ref).group(1))  # type: ignore[union-attr]
            _configured_project(runtime, project_id)
        elif self.project is not None:
            project_id = _configured_project(runtime, self.project)
        else:
            project_id, checkout = _checkout_by_path(runtime, self.path or "")
            if checkout == "default":
                checkout = None
        return ResolvedCheckout(
            project_id=project_id,
            checkout_id=checkout,
            ref=checkout_ref(project_id, checkout or "default"),
            project_ref=project_ref(project_id),
            checkout_ref=checkout_ref(project_id, checkout or "default"),
        )


class BeadLocator(GatewayModel):
    """A Beads task by canonical ref, id, or a title fragment within a project."""

    ref: str | None = Field(
        default=None, pattern=r"^sinnix://projects/[^/]+/beads/[^/]+$"
    )
    id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Bead id such as sinnix-abc1; the project is inferred from the prefix unless given.",
    )
    project: str | None = Field(default=None, min_length=1, max_length=128)
    title_contains: str | None = Field(
        default=None,
        min_length=1,
        max_length=512,
        description="Case-insensitive title fragment; requires project and must match exactly one bead.",
    )

    @model_validator(mode="after")
    def exactly_one(self) -> BeadLocator:
        if sum(v is not None for v in (self.ref, self.id, self.title_contains)) != 1:
            raise ValueError("give exactly one of ref, id or title_contains")
        if self.ref is not None and self.project is not None:
            raise ValueError("ref already names the project")
        if self.title_contains is not None and self.project is None:
            raise ValueError("title_contains requires project")
        return self

    def resolve(self, runtime: Any) -> tuple[str, str, str]:
        """Return ``(project_id, bead_id, ref)``."""
        if self.ref is not None:
            match = BEAD_REF.match(self.ref)
            assert match is not None
            project_id = _configured_project(runtime, unquote(match.group(1)))
            return project_id, unquote(match.group(2)), self.ref
        if self.id is not None:
            if self.project is not None:
                project_id = _configured_project(runtime, self.project)
            else:
                prefix = self.id.rsplit("-", 1)[0]
                if prefix not in runtime.config.projects:
                    raise ProtocolError(
                        "invalid_request",
                        "bead id prefix is not a configured project; pass project",
                        details={"id": self.id},
                    )
                project_id = prefix
            return project_id, self.id, bead_ref(project_id, self.id)
        project_id = _configured_project(runtime, self.project or "")
        rows = runtime.beads.query(
            project_ids=[project_id],
            view="all",
            native_filters={"title_contains": self.title_contains},
            limit=20,
        )["items"]
        if not rows:
            raise not_found("bead", self.model_dump(exclude_none=True))
        if len(rows) > 1:
            raise ambiguous(
                "bead",
                [
                    Candidate(
                        ref=row["ref"],
                        label=str(row.get("fields", {}).get("title", row["id"])),
                        detail={
                            "id": row["id"],
                            "status": row.get("fields", {}).get("status"),
                        },
                    )
                    for row in rows
                ],
            )
        return project_id, rows[0]["id"], rows[0]["ref"]


# ------------------------------------------------------------ desktop windows

WINDOW_REF_PREFIX = "sinnix://desktop/windows/"
TERMINAL_REF_PREFIX = "sinnix://terminals/"
PAGE_REF_PREFIX = "sinnix://browser/pages/"


def _ref_tail(ref: str, prefix: str, kind: str) -> str:
    if (
        not ref.startswith(prefix)
        or "/" in ref[len(prefix) :]
        or len(ref) == len(prefix)
    ):
        raise ProtocolError("invalid_request", f"ref is not a canonical {kind} ref")
    return ref[len(prefix) :]


def window_ref(address: str) -> str:
    return f"{WINDOW_REF_PREFIX}{address}"


def terminal_ref(kitty_id: int) -> str:
    return f"{TERMINAL_REF_PREFIX}{kitty_id}"


def page_ref(page_id: str) -> str:
    return f"{PAGE_REF_PREFIX}{page_id}"


def _pick(
    kind: str, locator: Any, matches: list[dict[str, Any]], label, ref
) -> dict[str, Any]:
    if not matches:
        raise not_found(kind, locator)
    if len(matches) > 1:
        raise ambiguous(
            kind,
            [
                Candidate(ref=ref(item), label=label(item), detail=item)
                for item in matches
            ],
        )
    return matches[0]


class WindowLocator(GatewayModel):
    """A Hyprland client by canonical ref, address, class/title, pid or focus."""

    ref: str | None = Field(
        default=None, pattern=r"^sinnix://desktop/windows/0x[0-9a-f]+$"
    )
    address: str | None = Field(default=None, pattern=r"^0x[0-9a-f]+$")
    class_: str | None = Field(
        default=None,
        alias="class",
        min_length=1,
        max_length=256,
        description="Exact window class (may combine with title_contains).",
    )
    title_contains: str | None = Field(default=None, min_length=1, max_length=512)
    pid: int | None = Field(default=None, ge=1)
    active: bool | None = Field(
        default=None, description="true selects the focused window."
    )

    model_config = {"extra": "forbid", "populate_by_name": True}

    @model_validator(mode="after")
    def exactly_one(self) -> WindowLocator:
        groups = [
            self.ref is not None,
            self.address is not None,
            self.pid is not None,
            self.active is True,
            self.class_ is not None or self.title_contains is not None,
        ]
        if sum(groups) != 1:
            raise ValueError(
                "give exactly one of ref, address, pid, active, or class/title_contains"
            )
        return self

    def resolve(self, runtime: Any) -> tuple[dict[str, Any], str]:
        """Return ``(client, canonical_ref)`` from the live client list."""
        clients = runtime.desktop.read("clients")["result"]
        if not isinstance(clients, list):
            raise ProtocolError(
                "owner_failed", "hypr control did not return a client list"
            )
        if self.ref is not None:
            address = _ref_tail(self.ref, WINDOW_REF_PREFIX, "window")
        else:
            address = self.address
        if address is not None:
            matches = [c for c in clients if c.get("address") == address]
        elif self.pid is not None:
            matches = [c for c in clients if c.get("pid") == self.pid]
        elif self.active:
            active = runtime.desktop.read("active_window")["result"]
            matches = [
                c for c in clients if c.get("address") == (active or {}).get("address")
            ]
        else:
            needle = (self.title_contains or "").casefold()
            matches = [
                c
                for c in clients
                if (self.class_ is None or c.get("class") == self.class_)
                and needle in str(c.get("title", "")).casefold()
            ]
        client = _pick(
            "window",
            self.model_dump(by_alias=True, exclude_none=True),
            matches,
            lambda c: f"{c.get('class', '')}: {c.get('title', '')}",
            lambda c: window_ref(str(c.get("address"))),
        )
        return client, window_ref(str(client["address"]))


class TerminalLocator(GatewayModel):
    """A kitty window by canonical ref, kitty id, title, cwd, pid or focus."""

    ref: str | None = Field(default=None, pattern=r"^sinnix://terminals/[0-9]+$")
    kitty_id: int | None = Field(default=None, ge=0)
    title_contains: str | None = Field(default=None, min_length=1, max_length=512)
    cwd: str | None = Field(default=None, min_length=1, max_length=4_096)
    pid: int | None = Field(default=None, ge=1, description="Shell pid of the window.")
    focused: bool | None = Field(default=None)

    @model_validator(mode="after")
    def exactly_one(self) -> TerminalLocator:
        given = [
            self.ref,
            self.kitty_id,
            self.title_contains,
            self.cwd,
            self.pid,
            True if self.focused else None,
        ]
        if sum(value is not None for value in given) != 1:
            raise ValueError(
                "give exactly one of ref, kitty_id, title_contains, cwd, pid, or focused"
            )
        return self

    @staticmethod
    def windows(listing: Any) -> list[dict[str, Any]]:
        """Flatten ``kitty @ ls`` into windows carrying their tab/os-window ids."""
        if not isinstance(listing, list):
            raise ProtocolError(
                "owner_failed", "kitty control did not return a window list"
            )
        flat: list[dict[str, Any]] = []
        for os_window in listing:
            for tab in os_window.get("tabs", []) or []:
                for window in tab.get("windows", []) or []:
                    flat.append(
                        {
                            **window,
                            "os_window_id": os_window.get("id"),
                            "tab_id": tab.get("id"),
                            "tab_title": tab.get("title"),
                            "focused": bool(
                                os_window.get("is_focused")
                                and tab.get("is_active")
                                and window.get("is_active")
                            ),
                        }
                    )
        return flat

    def resolve(self, runtime: Any) -> tuple[dict[str, Any], str]:
        windows = self.windows(runtime.terminals.read("list")["result"])
        kitty_id = self.kitty_id
        if self.ref is not None:
            kitty_id = int(_ref_tail(self.ref, TERMINAL_REF_PREFIX, "terminal"))
        if kitty_id is not None:
            matches = [w for w in windows if w.get("id") == kitty_id]
        elif self.pid is not None:
            matches = [w for w in windows if w.get("pid") == self.pid]
        elif self.focused:
            matches = [w for w in windows if w["focused"]]
        elif self.cwd is not None:
            matches = [
                w
                for w in windows
                if str(w.get("cwd", "")).rstrip("/") == self.cwd.rstrip("/")
            ]
        else:
            needle = (self.title_contains or "").casefold()
            matches = [
                w for w in windows if needle in str(w.get("title", "")).casefold()
            ]
        window = _pick(
            "terminal",
            self.model_dump(exclude_none=True),
            matches,
            lambda w: f"kitty {w.get('id')}: {w.get('title', '')} ({w.get('cwd', '')})",
            lambda w: terminal_ref(int(w.get("id"))),
        )
        return window, terminal_ref(int(window["id"]))


class PageLocator(GatewayModel):
    """A browser page by canonical ref, CDP page id, url or title fragment."""

    ref: str | None = Field(
        default=None, pattern=r"^sinnix://browser/pages/[A-Za-z0-9_-]+$"
    )
    page_id: str | None = Field(default=None, min_length=1, max_length=256)
    url_contains: str | None = Field(default=None, min_length=1, max_length=2_048)
    title_contains: str | None = Field(default=None, min_length=1, max_length=512)

    @model_validator(mode="after")
    def exactly_one(self) -> PageLocator:
        given = [self.ref, self.page_id, self.url_contains, self.title_contains]
        if sum(value is not None for value in given) != 1:
            raise ValueError(
                "give exactly one of ref, page_id, url_contains, or title_contains"
            )
        return self

    def resolve(self, pages: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
        """Pick one page from a listing; the caller decides which pages are eligible."""
        page_id = self.page_id
        if self.ref is not None:
            page_id = _ref_tail(self.ref, PAGE_REF_PREFIX, "page")
        if page_id is not None:
            matches = [p for p in pages if p.get("id") == page_id]
        elif self.url_contains is not None:
            matches = [p for p in pages if self.url_contains in str(p.get("url", ""))]
        else:
            needle = (self.title_contains or "").casefold()
            matches = [p for p in pages if needle in str(p.get("title", "")).casefold()]
        page = _pick(
            "page",
            self.model_dump(exclude_none=True),
            matches,
            lambda p: f"{p.get('title', '')} — {p.get('url', '')}",
            lambda p: page_ref(str(p.get("id"))),
        )
        return page, page_ref(str(page["id"]))


# ------------------------------------------------------------------- jobs

JOB_REF = re.compile(r"^sinnix://jobs/(\d+)$")


def job_ref(job_id: int | str) -> str:
    return f"sinnix://jobs/{int(job_id)}"


class JobLocator(GatewayModel):
    """A queued job by canonical ref or pueue task id."""

    ref: str | None = Field(
        default=None,
        pattern=r"^sinnix://jobs/\d+$",
        description="Canonical job ref returned by a run or list.",
    )
    job_id: int | None = Field(
        default=None,
        ge=0,
        description="pueue task id, as `agentctl job list` shows it.",
    )

    @model_validator(mode="after")
    def exactly_one(self) -> JobLocator:
        if (self.ref is None) == (self.job_id is None):
            raise ValueError("give exactly one of ref or job_id")
        return self

    def resolve(self) -> tuple[int, str]:
        """Return ``(pueue task id, canonical ref)`` without touching the queue."""
        if self.ref is not None:
            match = JOB_REF.match(self.ref)
            assert match is not None
            return int(match.group(1)), self.ref
        assert self.job_id is not None
        return self.job_id, job_ref(self.job_id)


# ------------------------------------------------------------------ machine


UNIT_REF_PREFIX = "sinnix://machine/units/"
PROCESS_REF_PREFIX = "sinnix://processes/"
MCP_TOOL_REF_PREFIX = "sinnix://mcp/"
UnitScope = Literal["user", "system"]


class UnitLocator(GatewayModel):
    """A systemd unit by canonical ref or by name and manager scope."""

    ref: str | None = Field(
        default=None,
        pattern=r"^sinnix://machine/units/(user|system)/[^/]{1,256}$",
        description="Canonical unit ref: sinnix://machine/units/<user|system>/<unit>.",
    )
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Unit name; a bare name without a type suffix means <name>.service.",
    )
    scope: UnitScope = Field(default="user", description="Manager owning the unit.")

    @model_validator(mode="after")
    def exactly_one(self) -> UnitLocator:
        if (self.name is None) == (self.ref is None):
            raise ValueError("give exactly one of name or ref")
        return self

    def resolve(self) -> tuple[str, UnitScope, str]:
        """Return ``(unit, scope, canonical_ref)`` without touching systemd."""
        if self.ref is not None:
            scope, _, unit = self.ref[len(UNIT_REF_PREFIX) :].partition("/")
            return unit, scope, self.ref  # type: ignore[return-value]
        unit = self.name or ""
        if "." not in unit:
            unit = f"{unit}.service"
        return unit, self.scope, f"{UNIT_REF_PREFIX}{self.scope}/{unit}"


def process_ref(pid: int, start_ticks: int) -> str:
    return f"{PROCESS_REF_PREFIX}{pid}/{start_ticks}"


def proc_row(pid: int) -> dict[str, Any] | None:
    """Identity fields of one live process from /proc, or None if it is gone."""
    base = Path("/proc") / str(pid)
    try:
        stat = (base / "stat").read_text()
        cgroup = (base / "cgroup").read_text().strip().rpartition(":")[2]
    except OSError:
        return None
    head, _, tail = stat.rpartition(")")
    comm = head.partition("(")[2]
    fields = tail.split()
    if len(fields) < 20:
        return None
    unit = next(
        (
            segment
            for segment in reversed(cgroup.split("/"))
            if segment.endswith((".service", ".scope"))
        ),
        None,
    )
    return {
        "pid": pid,
        "ppid": int(fields[1]),
        "comm": comm,
        "state": fields[0],
        "start_ticks": int(fields[19]),
        "cgroup": cgroup,
        "unit": unit,
    }


def proc_snapshot() -> list[dict[str, Any]]:
    rows = []
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            row = proc_row(int(entry.name))
            if row is not None:
                rows.append(row)
    rows.sort(key=lambda row: row["pid"])
    return rows


class ProcessLocator(GatewayModel):
    """A live process by canonical ref, pid, executable name or owning unit."""

    ref: str | None = Field(
        default=None, pattern=r"^sinnix://processes/[0-9]{1,10}/[0-9]{1,20}$"
    )
    pid: int | None = Field(default=None, ge=1)
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Exact kernel comm (executable base name, 15 chars max).",
    )
    unit: UnitLocator | None = Field(
        default=None, description="The systemd unit whose cgroup owns the process."
    )

    @model_validator(mode="after")
    def exactly_one(self) -> ProcessLocator:
        given = [v for v in (self.ref, self.pid, self.name, self.unit) if v is not None]
        if len(given) != 1:
            raise ValueError("give exactly one of ref, pid, name or unit")
        return self

    def resolve(self) -> tuple[dict[str, Any], str]:
        """Return ``(identity_row, canonical_ref)`` for exactly one live process."""
        if self.ref is not None:
            pid, _, ticks = self.ref[len(PROCESS_REF_PREFIX) :].partition("/")
            row = proc_row(int(pid))
            if row is None or row["start_ticks"] != int(ticks):
                raise not_found("process", self.ref)
            return row, self.ref
        if self.pid is not None:
            row = proc_row(self.pid)
            if row is None:
                raise not_found("process", self.pid)
            return row, process_ref(row["pid"], row["start_ticks"])
        if self.name is not None:
            rows = [row for row in proc_snapshot() if row["comm"] == self.name]
            locator: Any = self.name
        else:
            assert self.unit is not None
            unit, _scope, locator = self.unit.resolve()
            rows = [row for row in proc_snapshot() if row["unit"] == unit]
        if not rows:
            raise not_found("process", locator)
        if len(rows) > 1:
            raise ambiguous(
                "process",
                [
                    Candidate(
                        ref=process_ref(row["pid"], row["start_ticks"]),
                        label=f"{row['pid']} {row['comm']}",
                        detail={"unit": row["unit"], "ppid": row["ppid"]},
                    )
                    for row in rows
                ],
            )
        return rows[0], process_ref(rows[0]["pid"], rows[0]["start_ticks"])


class McpToolLocator(GatewayModel):
    """A brokered upstream MCP tool by canonical ref or server and tool name."""

    ref: str | None = Field(
        default=None, pattern=r"^sinnix://mcp/[^/]{1,128}/tools/[^/]{1,256}$"
    )
    server: str | None = Field(default=None, min_length=1, max_length=128)
    tool: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def exactly_one(self) -> McpToolLocator:
        if (self.ref is None) == (self.server is None or self.tool is None):
            raise ValueError("give either ref or both server and tool")
        if self.ref is not None and (self.server is not None or self.tool is not None):
            raise ValueError("give either ref or both server and tool")
        return self

    def resolve(self) -> tuple[str, str, str]:
        """Return ``(server, tool, canonical_ref)``."""
        if self.ref is not None:
            server, _, tool = self.ref[len(MCP_TOOL_REF_PREFIX) :].partition("/tools/")
            return server, tool, self.ref
        assert self.server is not None and self.tool is not None
        return (
            self.server,
            self.tool,
            f"{MCP_TOOL_REF_PREFIX}{self.server}/tools/{self.tool}",
        )


ARTIFACT_REF_PREFIX = "sinnix://artifacts/"


class ArtifactLocator(GatewayModel):
    """A gateway artifact by canonical ref or bare artifact id."""

    ref: str | None = Field(
        default=None, pattern=r"^sinnix://artifacts/[0-9a-fA-F-]{36}$"
    )
    artifact_id: str | None = Field(default=None, min_length=36, max_length=36)

    @model_validator(mode="after")
    def exactly_one(self) -> ArtifactLocator:
        if (self.ref is None) == (self.artifact_id is None):
            raise ValueError("give exactly one of ref or artifact_id")
        return self

    def resolve(self) -> tuple[str, str]:
        """Return ``(artifact_id, canonical_ref)``."""
        if self.ref is not None:
            return self.ref[len(ARTIFACT_REF_PREFIX) :], self.ref
        return self.artifact_id or "", f"{ARTIFACT_REF_PREFIX}{self.artifact_id}"
