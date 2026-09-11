"""Read-only Beads SQL plans and bounded, immutable analytical snapshots.

The canonical owner executes every query. This module never opens a database or
accepts SQL from callers; table names, columns and operators are allowlisted.
"""

from __future__ import annotations

import json
import re
from collections import Counter, deque
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from .beads import BeadsError

SUMMARY = (
    "id",
    "title",
    "status",
    "priority",
    "issue_type",
    "assignee",
    "owner",
    "created_at",
    "updated_at",
    "closed_at",
    "metadata",
    "defer_until",
    "due_at",
)
COLUMNS = {
    **{name: name for name in SUMMARY},
    "type": "issue_type",
    "created": "created_at",
    "updated": "updated_at",
    "closed": "closed_at",
    "started": "started_at",
    "template": "is_template",
    "spec": "spec_id",
    "description": "description",
    "notes": "notes",
    "pinned": "pinned",
    "ephemeral": "ephemeral",
    "mol_type": "mol_type",
    "external_ref": "external_ref",
    "wisp_type": "wisp_type",
}
RELATIONS = {
    name: name.replace("_", "-")
    for name in (
        "discovered_from",
        "split_from",
        "supersedes",
        "residual_of",
        "parent_child",
    )
}
PROVENANCE_RELATIONS = frozenset(
    {"discovered-from", "split-from", "supersedes", "residual-of"}
)
TOKEN = re.compile(r'\s*(>=|<=|!=|=|>|<|\(|\)|"(?:[^"\\]|\\.)*"|[^\s()=<>!]+)')


def literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        if not re.fullmatch(r"-?\d+(?:\.\d+)?", str(value)):
            raise BeadsError("invalid numeric filter")
        return str(value)
    if not isinstance(value, str) or len(value) > 4000:
        raise BeadsError("invalid filter literal")
    # Hex text literals are independent of the owner's backslash SQL mode.
    return "CONVERT(0x" + value.encode().hex() + " USING utf8mb4)" if value else "''"


def instant(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BeadsError("time must be an RFC3339 timestamp with timezone") from exc
    if result.tzinfo is None:
        raise BeadsError("time must include an explicit timezone")
    return result.astimezone(timezone.utc)


def relation(value: str) -> str:
    return RELATIONS.get(value, value)


class Analytics:
    def __init__(self, service: Any, project: Any, revision: str | None = None):
        self.service, self.project, self.revision = service, project, revision
        self.evaluation_time = datetime.now(timezone.utc)

    def now(self) -> str:
        return literal(self.evaluation_time.strftime("%Y-%m-%d %H:%M:%S.%f"))

    def sql(self, statement: str) -> list[dict[str, Any]]:
        rows = self.service._run(self.project, ["sql", statement], False)
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise BeadsError("owner SQL did not return rows", "owner_failed")
        return rows

    def table(self, name: str) -> str:
        if name not in {"issues", "dependencies", "comments", "labels"}:
            raise BeadsError("unsupported analytical table")
        suffix = ""
        if self.revision is not None:
            if not re.fullmatch(r"[a-zA-Z0-9]{16,64}", self.revision):
                raise BeadsError(
                    "owner returned an invalid exact revision", "owner_failed"
                )
            suffix = f" AS OF '{self.revision}'"
        return name + suffix

    def resolve(self, at: str) -> dict[str, Any]:
        if re.match(r"^\d{4}-\d{2}-\d{2}", at):
            requested = instant(at)
            self.evaluation_time = requested
            # DOLT_LOG('HEAD') enumerates reachable commits. commit_order breaks
            # equal commit-clock timestamps using the owner's topology order.
            rows = self.sql(
                "SELECT commit_hash, DATE_FORMAT(date, '%Y-%m-%dT%H:%i:%s.%fZ') "
                "AS committed_at, commit_order FROM DOLT_LOG('HEAD') WHERE date <= "
                + literal(requested.strftime("%Y-%m-%d %H:%M:%S.%f"))
                + " ORDER BY date DESC, commit_order DESC LIMIT 2"
            )
            if not rows:
                raise BeadsError(
                    "no reachable revision at or before requested time", "not_found"
                )
            if (
                len(rows) > 1
                and rows[0].get("committed_at") == rows[1].get("committed_at")
                and (
                    rows[0].get("commit_order") is None
                    or rows[0].get("commit_order") == rows[1].get("commit_order")
                )
            ):
                raise BeadsError(
                    "owner cannot disambiguate equal-time revisions", "invalid_request"
                )
            selected = rows[0]
        else:
            if not re.fullmatch(r"[A-Za-z0-9_./~^{}@-]{1,128}", at):
                raise BeadsError("invalid historical revision selector")
            rows = self.sql("SELECT DOLT_HASHOF(" + literal(at) + ") AS commit_hash")
            if len(rows) != 1:
                raise BeadsError("revision selector did not resolve", "not_found")
            selected = rows[0]
        self.revision = str(selected.get("commit_hash", ""))
        self.table("issues")  # Validate the owner's resolved hash before interpolation.
        return {
            "requested": at,
            "resolved_revision": self.revision,
            "effective_at": selected.get("committed_at"),
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "known_at": None,
            "watermark": self.revision,
            "semantics": (
                "latest_reachable_commit_at_or_before"
                if re.match(r"^\d{4}-", at)
                else "exact_revision"
            ),
        }

    def atom(self, field: str, op: str, value: Any) -> str:
        if op not in {"=", "!=", ">", ">=", "<", "<="}:
            raise BeadsError("filter operator is unsupported")
        if field == "label":
            predicate = "l.issue_id=i.id"
            if value != "none":
                predicate += " AND l.label=" + literal(value)
            exists = (
                f"EXISTS (SELECT 1 FROM {self.table('labels')} l WHERE {predicate})"
            )
            if op not in {"=", "!="}:
                raise BeadsError("label supports equality only")
            return ("NOT " if (value == "none") != (op == "!=") else "") + exists
        if field == "parent":
            if op not in {"=", "!="}:
                raise BeadsError("parent supports equality only")
            return (
                ("NOT " if op == "!=" else "")
                + f"EXISTS (SELECT 1 FROM {self.table('dependencies')} d WHERE d.issue_id=i.id AND d.type='parent-child' AND d.depends_on_issue_id="
                + literal(value)
                + ")"
            )
        if field not in COLUMNS:
            raise BeadsError(
                f"unsupported filter field: {field}", "unsupported_capability"
            )
        column = "i." + COLUMNS[field]
        if field in {
            "created",
            "updated",
            "closed",
            "started",
            "due_at",
            "defer_until",
        } and isinstance(value, str):
            duration = re.fullmatch(r"(\d+)([hdw])", value)
            if duration:
                hours = int(duration[1]) * {"h": 1, "d": 24, "w": 168}[duration[2]]
                value = (self.evaluation_time - timedelta(hours=hours)).strftime(
                    "%Y-%m-%d %H:%M:%S.%f"
                )
            elif "T" in value:
                value = instant(value).strftime("%Y-%m-%d %H:%M:%S.%f")
            elif not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise BeadsError(
                    "date requires RFC3339, YYYY-MM-DD, or an h/d/w duration",
                    "unsupported_capability",
                )
        if value == "none" and field in {"assignee", "description"}:
            return f"COALESCE({column}, '') {'<>' if op == '!=' else '='} ''"
        if field in {"title", "description", "notes"} and op in {"=", "!="}:
            return (
                f"LOWER(COALESCE({column}, '')) {'NOT LIKE' if op == '!=' else 'LIKE'} "
                + literal(
                    "%"
                    + str(value)
                    .replace("\\", "\\\\")
                    .replace("%", "\\%")
                    .replace("_", "\\_")
                    + "%"
                )
            )
        if field in {"id", "spec"} and isinstance(value, str) and "*" in value:
            return (
                column
                + (" NOT LIKE " if op == "!=" else " LIKE ")
                + literal(
                    value.replace("%", "\\%").replace("_", "\\_").replace("*", "%")
                )
            )
        return f"{column}{op}{literal(value)}"

    def ast(self, node: Mapping[str, Any]) -> str:
        if not isinstance(node, Mapping):
            raise BeadsError("filter node must be an object")
        if not node:
            return "TRUE"
        if set(node) in ({"and"}, {"or"}):
            kind = next(iter(node))
            if not isinstance(node[kind], list) or not node[kind]:
                raise BeadsError("boolean filter requires children")
            return (
                "("
                + (" " + kind.upper() + " ").join(
                    self.ast(child) for child in node[kind]
                )
                + ")"
            )
        if set(node) == {"not"}:
            return "NOT (" + self.ast(node["not"]) + ")"
        return " AND ".join(
            (
                self.atom(key, value.get("op", "="), value.get("value"))
                if isinstance(value, Mapping)
                else self.atom(key, "=", value)
            )
            for key, value in node.items()
        )

    def expression(self, expression: str) -> str:
        tokens, end = [], 0
        for match in TOKEN.finditer(expression):
            if match.start() != end:
                raise BeadsError("invalid native expression")
            tokens.append(match[1])
            end = match.end()
        if expression[end:].strip():
            raise BeadsError("invalid native expression")
        position = 0

        def parse(level: int = 0) -> str:
            nonlocal position
            if level < 2:
                result = parse(level + 1)
                operator = ("OR", "AND")[level]
                while position < len(tokens) and tokens[position].upper() == operator:
                    position += 1
                    result = f"({result} {operator} {parse(level + 1)})"
                return result
            if position >= len(tokens):
                raise BeadsError("incomplete native expression")
            token = tokens[position]
            position += 1
            if token.upper() == "NOT":
                return "NOT (" + parse(2) + ")"
            if token == "(":
                result = parse()
                if position >= len(tokens) or tokens[position] != ")":
                    raise BeadsError("unbalanced native expression")
                position += 1
                return "(" + result + ")"
            if position + 1 >= len(tokens):
                raise BeadsError("incomplete native comparison")
            op, value = tokens[position : position + 2]
            position += 2
            if value.startswith('"'):
                value = json.loads(value)
            elif value in {"true", "false"}:
                value = value == "true"
            elif re.fullmatch(r"\d+", value):
                value = int(value)
            return self.atom(token, op, value)

        result = parse()
        if position != len(tokens):
            raise BeadsError("unexpected native expression tokens")
        return result

    def blockers(self) -> str:
        return f"EXISTS (SELECT 1 FROM {self.table('dependencies')} d LEFT JOIN {self.table('issues')} b ON b.id=d.depends_on_issue_id WHERE d.issue_id=i.id AND d.type='blocks' AND (b.id IS NULL OR b.status NOT IN ('closed','tombstone')))"

    def native(self, values: Mapping[str, Any]) -> list[str]:
        result = []
        for key, value in values.items():
            if value is None:
                continue
            if isinstance(value, bool) and not value:
                raise BeadsError("native boolean filters must be true when supplied")
            if key in {
                "all",
                "include_gates",
                "include_infra",
                "include_templates",
                "include_ephemeral",
                "include_deferred",
                "stale_days",
            }:
                continue
            if key in {"label", "exclude_label", "label_any", "exclude_type"}:
                field = "type" if key == "exclude_type" else "label"
                result.append(
                    "("
                    + (" OR " if key == "label_any" else " AND ").join(
                        self.atom(
                            field, "!=" if key.startswith("exclude") else "=", item
                        )
                        for item in value
                    )
                    + ")"
                )
            elif key in {"priority_min", "priority_max", "priority"}:
                result.append(
                    self.atom(
                        "priority",
                        {"priority_min": ">=", "priority_max": "<="}.get(key, "="),
                        int(str(value).upper().removeprefix("P")),
                    )
                )
            elif key == "status":
                result.append(
                    "("
                    + " OR ".join(
                        self.atom("status", "=", item) for item in value.split(",")
                    )
                    + ")"
                )
            elif key == "id":
                result.append(
                    "("
                    + " OR ".join(
                        self.atom("id", "=", item) for item in value.split(",")
                    )
                    + ")"
                )
            elif key == "spec":
                result.append(
                    "i.spec_id LIKE "
                    + literal(value.replace("%", "\\%").replace("_", "\\_") + "%")
                )
            elif key.endswith(("_after", "_before")):
                field, boundary = key.rsplit("_", 1)
                field = {"due": "due_at", "defer": "defer_until"}.get(field, field)
                result.append(
                    self.atom(field, ">" if boundary == "after" else "<", value)
                )
            elif key in {
                "title_contains",
                "desc_contains",
                "notes_contains",
                "empty_description",
            }:
                field = {
                    "title_contains": "title",
                    "desc_contains": "description",
                    "notes_contains": "notes",
                    "empty_description": "description",
                }[key]
                result.append(
                    self.atom(
                        field, "=", "none" if key == "empty_description" else value
                    )
                )
            elif key in {"no_assignee", "unassigned", "no_labels"}:
                result.append(
                    self.atom(
                        "label" if key == "no_labels" else "assignee", "=", "none"
                    )
                )
            elif key in {"pinned", "no_pinned"}:
                result.append(self.atom("pinned", "=", key == "pinned"))
            elif key == "no_parent":
                result.append(
                    f"NOT EXISTS (SELECT 1 FROM {self.table('dependencies')} d WHERE d.issue_id=i.id AND d.type='parent-child')"
                )
            elif key == "deferred":
                result.append("i.defer_until IS NOT NULL")
            elif key == "overdue":
                result.append("i.due_at < " + self.now() + " AND i.status <> 'closed'")
            elif key in {"ready", "gated"}:
                result.append(("NOT " if key == "ready" else "") + self.blockers())
            elif key in {"has_metadata_key", "metadata_field"}:
                items = [value] if key == "has_metadata_key" else value
                for item in items:
                    metadata_key, _, expected = item.partition("=")
                    path = literal("$." + json.dumps(metadata_key))
                    extract = f"JSON_EXTRACT(i.metadata, {path})"
                    result.append(
                        f"{extract} IS NOT NULL"
                        if key == "has_metadata_key"
                        else f"JSON_UNQUOTE({extract})=" + literal(expected)
                    )
            elif key in {"label_pattern", "label_regex"}:
                operator = "REGEXP" if key == "label_regex" else "LIKE"
                pattern = (
                    value
                    if key == "label_regex"
                    else value.replace("%", "\\%")
                    .replace("_", "\\_")
                    .replace("*", "%")
                    .replace("?", "_")
                )
                result.append(
                    f"EXISTS (SELECT 1 FROM {self.table('labels')} l WHERE l.issue_id=i.id AND l.label {operator} {literal(pattern)})"
                )
            elif key == "external_contains":
                result.append("i.external_ref LIKE " + literal("%" + value + "%"))
            elif key in COLUMNS or key == "parent":
                result.append(self.atom(key, "=", value))
            else:
                raise BeadsError(
                    f"unsupported native filter: {key}", "unsupported_capability"
                )
        return result

    def select(
        self,
        *,
        view: str,
        filters: Mapping[str, Any],
        expression: str | None,
        native: Mapping[str, Any],
        order: Mapping[str, Any],
        projection: str,
        aggregate: Mapping[str, Any] | None,
        max_rows: int,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        predicates = [self.ast(filters), *self.native(native)]
        if expression:
            predicates.append(self.expression(expression))
        if view == "query" and not (filters or expression or native):
            raise BeadsError("query requires filters, expression or native_filters")
        views = {
            "query",
            "all",
            "open",
            "ready",
            "blocked",
            "recent",
            "overdue",
            "deferred",
            "unassigned",
            "stale_claims",
            "epic_progress",
            "changed_since",
        }
        if view not in views:
            raise BeadsError("unsupported query view")
        if view == "open":
            predicates.append("i.status='open'")
        if view in {"ready", "blocked"}:
            predicates.append(("NOT " if view == "ready" else "") + self.blockers())
        if view == "ready":
            predicates.append("i.status='open'")
        if view == "deferred":
            predicates.append("i.defer_until IS NOT NULL")
        if view == "overdue":
            predicates.append("i.due_at < " + self.now() + " AND i.status <> 'closed'")
        if view == "unassigned":
            predicates.append("COALESCE(i.assignee,'')=''")
        if view == "epic_progress":
            predicates.append("i.issue_type='epic'")
        if view == "stale_claims":
            predicates += [
                "i.status='in_progress'",
                self.atom("updated", "<", str(native.get("stale_days", 30)) + "d"),
            ]
        if view == "changed_since" and "updated_after" not in native:
            raise BeadsError("changed_since requires updated_after")
        if view not in {"all", "query"} and not native.get("all"):
            predicates.append("i.status NOT IN ('closed','tombstone')")
        if (
            not native.get("include_deferred")
            and view not in {"all", "deferred"}
            and not native.get("deferred")
        ):
            predicates.append(
                "(i.defer_until IS NULL OR i.defer_until<=" + self.now() + ")"
            )
        for option, predicate in {
            "include_gates": "i.issue_type <> 'gate'",
            "include_infra": "i.issue_type NOT IN ('agent','role','message')",
            "include_templates": "COALESCE(i.is_template,FALSE)=FALSE",
            "include_ephemeral": "COALESCE(i.ephemeral,FALSE)=FALSE",
        }.items():
            if not native.get(option) and not (
                option == "include_gates" and native.get("type") == "gate"
            ):
                predicates.append(predicate)
        base = f" FROM {self.table('issues')} i WHERE " + " AND ".join(
            "(" + item + ")" for item in predicates
        )
        count = self.sql("SELECT COUNT(*) AS count" + base)
        total = int(count[0]["count"])
        if aggregate is not None:
            if set(aggregate) - {"group_by"}:
                raise BeadsError("aggregate supports only group_by")
            groups = aggregate.get("group_by", [])
            if not isinstance(groups, list) or any(
                item not in {"status", "type", "priority", "assignee", "owner"}
                for item in groups
            ):
                raise BeadsError("unsupported grouping")
            columns = ["i." + COLUMNS[item] for item in groups]
            rows = self.sql(
                "SELECT "
                + ", ".join(columns + ["COUNT(*) AS count"])
                + base
                + (
                    " GROUP BY "
                    + ", ".join(columns)
                    + " ORDER BY "
                    + ", ".join(columns)
                    if columns
                    else ""
                )
                + f" LIMIT {max_rows + 1}"
            )
            return rows[:max_rows], {
                "total": total,
                "total_exact": True,
                "truncated": len(rows) > max_rows,
                "aggregate": True,
            }
        if total > max_rows:
            raise BeadsError(
                f"query has {total} rows; narrow filters or use aggregate (snapshot bound {max_rows})",
                "response_bound",
            )
        field = order.get("field", "updated" if view == "recent" else "priority")
        if field not in {
            "priority",
            "created",
            "updated",
            "closed",
            "status",
            "id",
            "title",
            "type",
            "assignee",
        }:
            raise BeadsError("unsupported ordering")
        descending = (field in {"created", "updated", "closed"}) != bool(
            order.get("reverse", False)
        )
        selected = (
            "i.*"
            if projection == "full"
            else ", ".join("i." + name for name in SUMMARY)
        )
        rows = self.sql(
            "SELECT "
            + selected
            + base
            + " ORDER BY i."
            + COLUMNS[field]
            + (" DESC" if descending else " ASC")
            + ", i.id ASC"
            + f" LIMIT {max_rows + 1}"
        )
        if len(rows) > max_rows:
            raise BeadsError(
                "owner changed beyond snapshot row bound", "source_changed"
            )
        return rows, {"total": total, "total_exact": True, "truncated": False}

    def includes(self, bead_id: str, names: set[str]) -> dict[str, Any]:
        result = {}
        for name in sorted(names):
            if name == "comments":
                statement = f"SELECT * FROM {self.table('comments')} WHERE issue_id={literal(bead_id)} ORDER BY created_at, id LIMIT 201"
            elif name in {"dependencies", "dependents", "children", "blockers"}:
                reverse = name in {"dependents", "children"}
                source, target = (
                    ("depends_on_issue_id", "issue_id")
                    if reverse
                    else ("issue_id", "depends_on_issue_id")
                )
                statement = f"SELECT i.*, d.type AS dependency_type FROM {self.table('dependencies')} d LEFT JOIN {self.table('issues')} i ON i.id=d.{target} WHERE d.{source}={literal(bead_id)}"
                if name == "children":
                    statement += " AND d.type='parent-child'"
                if name == "blockers":
                    statement += " AND d.type='blocks' AND (i.id IS NULL OR i.status NOT IN ('closed','tombstone'))"
                statement += " ORDER BY i.id LIMIT 201"
            else:
                result[name] = {
                    "state": "unavailable",
                    "reason": "owner does not expose this include at an exact historical revision",
                    "revision": self.revision,
                }
                continue
            try:
                rows = self.sql(statement)
                result[name] = {
                    "state": "complete" if len(rows) <= 200 else "partial",
                    "items": rows[:200],
                    "count": len(rows[:200]),
                    "truncated": len(rows) > 200,
                    "revision": self.revision,
                }
            except BeadsError as exc:
                result[name] = {
                    "state": "unavailable",
                    "reason": str(exc),
                    "revision": self.revision,
                }
        return result

    def provenance(
        self, nodes: list[str], *, max_edges: int, membership_complete: bool
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Read provenance touching members without expanding membership.

        Native dependency direction is retained: issue_id -> depends_on_*.
        Chunking keeps compiled SQL arguments below the host argv byte bound.
        """
        edges, frontier = {}, []
        kinds = ",".join(literal(kind) for kind in sorted(PROVENANCE_RELATIONS))
        for offset in range(0, len(nodes), 100):
            selected = ",".join(
                literal(node) for node in sorted(nodes)[offset : offset + 100]
            )
            statement = (
                "SELECT issue_id, depends_on_issue_id, depends_on_wisp_id, depends_on_external, type "
                f"FROM {self.table('dependencies')} WHERE type IN ({kinds}) "
                f"AND (issue_id IN ({selected}) OR depends_on_issue_id IN ({selected})) "
                "ORDER BY issue_id, depends_on_issue_id, depends_on_external, depends_on_wisp_id, type "
                f"LIMIT {max_edges + 1}"
            )
            try:
                rows = self.sql(statement)
            except BeadsError as exc:
                frontier.append(
                    {
                        "reason": "owner_unavailable",
                        "error": str(exc),
                        "members": sorted(nodes)[offset : offset + 100],
                    }
                )
                continue
            for row in rows:
                kind = row.get("type")
                if kind not in PROVENANCE_RELATIONS:
                    continue
                target_kind, target = next(
                    (
                        (name, row[column])
                        for name, column in (
                            ("bead", "depends_on_issue_id"),
                            ("external", "depends_on_external"),
                            ("wisp", "depends_on_wisp_id"),
                        )
                        if row.get(column) is not None
                    ),
                    ("unavailable", None),
                )
                key = (row["issue_id"], target_kind, target, kind)
                if key not in edges and len(edges) >= max_edges:
                    frontier.append({"reason": "edge_bound", "max_edges": max_edges})
                    break
                edges[key] = {
                    "from": row["issue_id"],
                    "to": target,
                    "relation": kind.replace("-", "_"),
                    "native_relation": kind,
                    "target_kind": target_kind,
                }
                if target is None:
                    frontier.append(
                        {
                            "reason": "missing_endpoint",
                            "from": row["issue_id"],
                            "relation": kind,
                        }
                    )
            if len(rows) > max_edges or any(
                item["reason"] == "edge_bound" for item in frontier
            ):
                if not any(item["reason"] == "edge_bound" for item in frontier):
                    frontier.append({"reason": "edge_bound", "max_edges": max_edges})
                break
        if not membership_complete:
            frontier.append({"reason": "membership_incomplete"})
        return list(edges.values()), {
            "state": "partial" if frontier else "complete",
            "complete": not frontier,
            "scope": "incoming_and_outgoing_edges_touching_members",
            "revision": self.revision,
            "returned": len(edges),
            "frontier": frontier,
        }

    def _closure_edges(
        self,
        members: list[str],
        *,
        direction: str,
        relation_filter: str | None,
        max_edges: int,
    ) -> dict[str, list[dict[str, Any]]]:
        selected = ",".join(literal(member) for member in members)
        join = {
            "prerequisites": "d.issue_id=m.id",
            "dependents": "d.depends_on_issue_id=m.id",
            "both": "(d.issue_id=m.id OR d.depends_on_issue_id=m.id)",
        }[direction]
        predicates = [
            "m.id IN (" + selected + ")",
            "d.type NOT IN ("
            + ",".join(literal(kind) for kind in sorted(PROVENANCE_RELATIONS))
            + ")",
        ]
        if relation_filter:
            predicates.append("d.type=" + literal(relation(relation_filter)))
        rows = self.sql(
            "SELECT owner_id, issue_id, depends_on_issue_id, depends_on_wisp_id, depends_on_external, type FROM ("
            "SELECT m.id AS owner_id, d.issue_id, d.depends_on_issue_id, d.depends_on_wisp_id, d.depends_on_external, d.type, "
            "ROW_NUMBER() OVER (PARTITION BY m.id ORDER BY d.issue_id, d.depends_on_issue_id, d.depends_on_external, d.depends_on_wisp_id, d.type, d.id) AS edge_rank "
            f"FROM {self.table('dependencies')} d JOIN {self.table('issues')} m ON {join} WHERE "
            + " AND ".join(predicates)
            + f") ranked WHERE edge_rank <= {max_edges + 1} ORDER BY owner_id, edge_rank LIMIT {len(members) * (max_edges + 1)}"
        )
        grouped = {member: [] for member in members}
        for row in rows:
            if (
                row.get("owner_id") not in grouped
                or not {"issue_id", "depends_on_issue_id", "type"} <= row.keys()
            ):
                raise BeadsError(
                    "owner omitted bounded edge ownership or fields", "owner_failed"
                )
            grouped[row["owner_id"]].append(row)
        return grouped

    def _closure_blockers(
        self, members: list[str], *, max_edges: int
    ) -> dict[str, list[dict[str, Any]]]:
        grouped = {member: [] for member in members}
        for offset in range(0, len(members), 100):
            chunk = members[offset : offset + 100]
            selected = ",".join(literal(member) for member in chunk)
            rows = self.sql(
                "SELECT owner_id, id, status FROM (SELECT d.issue_id AS owner_id, d.depends_on_issue_id AS id, b.status, "
                "ROW_NUMBER() OVER (PARTITION BY d.issue_id ORDER BY d.depends_on_issue_id, d.id) AS edge_rank "
                f"FROM {self.table('dependencies')} d LEFT JOIN {self.table('issues')} b ON b.id=d.depends_on_issue_id "
                f"WHERE d.issue_id IN ({selected}) AND d.type='blocks') ranked WHERE edge_rank <= {max_edges + 1} "
                f"ORDER BY owner_id, edge_rank LIMIT {len(chunk) * (max_edges + 1)}"
            )
            for row in rows:
                if (
                    row.get("owner_id") not in chunk
                    or not {"id", "status"} <= row.keys()
                ):
                    raise BeadsError(
                        "owner omitted bounded blocker ownership or fields",
                        "owner_failed",
                    )
                grouped[row["owner_id"]].append(row)
        return grouped

    def closure(
        self,
        roots: list[str],
        *,
        relation_filter: str | None,
        direction: str,
        max_nodes: int,
        max_depth: int,
    ) -> dict[str, Any]:
        nodes, edges, frontier = {}, {}, []
        incomplete_leaves = set()
        revision_unavailable_reason = None
        queue = deque((root, 0) for root in sorted(set(roots)))
        scheduled = set(roots)
        while queue:
            capacity = max_nodes - len(nodes)
            if capacity <= 0:
                frontier.extend(
                    {"id": node, "reason": "node_bound"} for node, _ in queue
                )
                break
            depth = queue[0][1]
            batch = []
            while queue and queue[0][1] == depth and len(batch) < min(100, capacity):
                batch.append(queue.popleft()[0])
            columns = ", ".join((*SUMMARY, "acceptance_criteria"))
            selected = ",".join(literal(node) for node in batch)
            source = f" FROM {self.table('issues')} WHERE id IN ({selected}) ORDER BY id LIMIT {len(batch)}"
            if revision_unavailable_reason is None:
                try:
                    # Beads NewIssueDetails exposes row_lock as the opaque
                    # equality-only revision. Cast before JSON serialization
                    # so int64 tokens never lose precision in other clients.
                    records = self.sql(
                        "SELECT "
                        + columns
                        + ", CAST(row_lock AS CHAR) AS bead_revision"
                        + source
                    )
                except BeadsError as exc:
                    revision_unavailable_reason = str(exc)
                    records = self.sql("SELECT " + columns + source)
            else:
                records = self.sql("SELECT " + columns + source)
            by_id = {row["id"]: row for row in records if row.get("id") in batch}
            members = []
            for node in batch:
                if node not in by_id:
                    frontier.append({"id": node, "reason": "missing"})
                    continue
                record = dict(by_id[node])
                token = record.get("bead_revision")
                token_known = (
                    isinstance(token, (str, int))
                    and not isinstance(token, bool)
                    and re.fullmatch(r"-?\d+", str(token)) is not None
                    and revision_unavailable_reason is None
                )
                record["bead_revision"] = str(token) if token_known else None
                record["bead_revision_domain"] = (
                    "beads_row_revision" if token_known else None
                )
                record["bead_revision_coverage"] = (
                    "partial_update_coverage" if token_known else "unavailable"
                )
                record["bead_revision_unavailable_reason"] = (
                    None
                    if token_known
                    else revision_unavailable_reason
                    or "owner omitted a valid row revision"
                )
                nodes[node] = record
                members.append(node)
            edge_groups = (
                self._closure_edges(
                    members,
                    direction=direction,
                    relation_filter=relation_filter,
                    max_edges=max_nodes,
                )
                if members
                else {}
            )
            for node in members:
                rows = edge_groups[node]
                if len(rows) > max_nodes:
                    incomplete_leaves.add(node)
                    frontier.append({"id": node, "reason": "edge_bound"})
                for row in rows[:max_nodes]:
                    source, target, kind = (
                        row["issue_id"],
                        row.get("depends_on_issue_id"),
                        row["type"],
                    )
                    if kind in PROVENANCE_RELATIONS:
                        continue
                    other = target if source == node else source
                    if target is None:
                        incomplete_leaves.add(node)
                        frontier.append(
                            {
                                "id": node,
                                "reason": "external_dependency",
                                "target": row.get("depends_on_external")
                                or row.get("depends_on_wisp_id"),
                            }
                        )
                        continue
                    edges[(source, target, kind)] = {
                        "from": source,
                        "to": target,
                        "relation": (
                            kind.replace("-", "_")
                            if kind in RELATIONS.values()
                            else kind
                        ),
                        "native_relation": kind,
                    }
                    if other not in scheduled:
                        scheduled.add(other)
                        if depth >= max_depth:
                            frontier.append({"id": other, "reason": "depth_bound"})
                        else:
                            queue.append((other, depth + 1))
        # Strongly connected components identify cycles even away from roots.
        adjacency = {node: [] for node in nodes}
        for source, target, _ in edges:
            if source in nodes and target in nodes:
                adjacency[source].append(target)
        visited, finished, cycles = set(), [], []
        for node in nodes:
            if node in visited:
                continue
            visited.add(node)
            stack = [(node, iter(adjacency[node]))]
            while stack:
                current, targets = stack[-1]
                other = next(targets, None)
                if other is None:
                    finished.append(current)
                    stack.pop()
                elif other not in visited:
                    visited.add(other)
                    stack.append((other, iter(adjacency[other])))
        reverse_edges = {node: [] for node in nodes}
        for source, targets in adjacency.items():
            for target in targets:
                reverse_edges[target].append(source)
        visited.clear()
        for node in reversed(finished):
            if node in visited:
                continue
            pending, component = [node], []
            visited.add(node)
            while pending:
                current = pending.pop()
                component.append(current)
                for other in reverse_edges[current]:
                    if other not in visited:
                        visited.add(other)
                        pending.append(other)
            if len(component) > 1 or node in adjacency[node]:
                cycles.append(sorted(component))
        gate_ids, decision_ids, unknown_roles, readiness = [], [], [], {}
        blocker_groups = self._closure_blockers(list(nodes), max_edges=max_nodes)
        for node, row in nodes.items():
            metadata = row.get("metadata") or {}
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except ValueError:
                    metadata = {}
            role = metadata.get("closure_role") if isinstance(metadata, dict) else None
            if row.get("issue_type") == "gate" or role == "gate":
                gate_ids.append(node)
            elif row.get("issue_type") == "decision" or role == "decision":
                decision_ids.append(node)
            elif role not in {"work", "leaf"}:
                unknown_roles.append(node)
            # Readiness is based on all blocking edges, independently of the
            # relationship selected for traversal; missing targets stay unknown.
            blocked = blocker_groups[node]
            unknown = (
                any(item.get("status") is None for item in blocked)
                or len(blocked) > max_nodes
            )
            open_blockers = [
                item["id"]
                for item in blocked
                if item.get("status") not in {None, "closed", "tombstone"}
            ]
            deferred = False
            if row.get("defer_until"):
                try:
                    deferred = instant(str(row["defer_until"])) > self.evaluation_time
                except BeadsError:
                    unknown = True
            readiness[node] = {
                "state": (
                    "closed"
                    if row.get("status") in {"closed", "tombstone"}
                    else (
                        "unknown"
                        if unknown
                        else (
                            "blocked"
                            if open_blockers
                            else (
                                "deferred"
                                if deferred or row.get("status") == "deferred"
                                else "ready"
                            )
                        )
                    )
                ),
                "blockers": open_blockers,
            }
        outgoing = dict.fromkeys(nodes, 0)
        for source, target, _ in edges:
            if direction in {"prerequisites", "both"} and source in outgoing:
                outgoing[source] += 1
            if direction in {"dependents", "both"} and target in outgoing:
                outgoing[target] += 1
        provenance_edges, provenance_coverage = self.provenance(
            list(nodes), max_edges=max_nodes * 4, membership_complete=not frontier
        )
        return {
            "roots": roots,
            "nodes": list(nodes.values()),
            "edges": list(edges.values()),
            "provenance_edges": provenance_edges,
            "provenance_coverage": provenance_coverage,
            "cycles": sorted(cycles),
            "graph_leaves": sorted(
                node
                for node, degree in outgoing.items()
                if degree == 0 and node not in incomplete_leaves
            ),
            "declared_gates": sorted(gate_ids),
            "declared_decisions": sorted(decision_ids),
            "unknown_roles": sorted(unknown_roles),
            "readiness": readiness,
            "frontier": frontier,
            "coverage": {
                "state": "partial" if frontier else "complete",
                "complete": not frontier,
            },
            "counts": {
                "nodes": len(nodes),
                "edges": len(edges),
                "provenance_edges": len(provenance_edges),
                "cycles": len(cycles),
                "statuses": dict(
                    Counter(row.get("status", "unknown") for row in nodes.values())
                ),
                "readiness": dict(Counter(row["state"] for row in readiness.values())),
            },
        }
