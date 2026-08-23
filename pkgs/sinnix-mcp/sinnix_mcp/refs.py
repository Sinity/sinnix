from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.parse import quote, unquote, urlsplit


class ReferenceError(ValueError):
    """Raised when a canonical Sinnix reference is malformed or ambiguous."""


@dataclass(frozen=True)
class SinnixRef:
    """A parsed canonical ``sinnix://`` resource reference.

    Resource identity is a URI, not a filesystem path. Parsing rejects inputs
    that could blur that boundary before an owner receives a reference.
    """

    segments: tuple[str, ...]

    scheme = "sinnix"

    @classmethod
    def parse(cls, value: str) -> "SinnixRef":
        parsed = urlsplit(value)
        if parsed.scheme != cls.scheme:
            raise ReferenceError(f"reference must use {cls.scheme}://")
        if parsed.query or parsed.fragment or parsed.username or parsed.password or parsed.port:
            raise ReferenceError("resource references cannot contain authority details, query, or fragment")
        if parsed.netloc:
            raw_segments = [parsed.netloc, *parsed.path.split("/")]
        else:
            raw_segments = parsed.path.split("/")
        segments = tuple(unquote(segment) for segment in raw_segments if segment)
        if not segments:
            raise ReferenceError("resource reference must name a resource")
        if any(segment in {".", ".."} for segment in segments):
            raise ReferenceError("resource reference cannot contain relative path segments")
        if any("/" in segment or "\\" in segment or "\x00" in segment for segment in segments):
            raise ReferenceError("resource reference segments cannot contain path separators or NUL")
        return cls(segments)

    def __str__(self) -> str:
        return f"{self.scheme}://{'/'.join(quote(segment, safe='') for segment in self.segments)}"


@dataclass(frozen=True)
class RefTemplate:
    """A typed URI template for one resource kind.

    Segment placeholders use ``{name}`` and consume exactly one escaped URI
    segment. They never expand into filesystem paths.
    """

    kind: str
    template: str

    def __post_init__(self) -> None:
        parsed = SinnixRef.parse(self.template.replace("{", "template-").replace("}", ""))
        if not self.kind:
            raise ReferenceError("resource kind cannot be empty")
        if not parsed.segments:
            raise ReferenceError("resource template cannot be empty")
        _ = self.variables

    @property
    def segments(self) -> tuple[str, ...]:
        return tuple(segment for segment in self.template.removeprefix("sinnix://").split("/") if segment)

    @property
    def variables(self) -> tuple[str, ...]:
        variables: list[str] = []
        for segment in self.segments:
            if segment.startswith("{") and segment.endswith("}"):
                name = segment[1:-1]
                if not name.isidentifier():
                    raise ReferenceError(f"invalid template variable: {name!r}")
                variables.append(name)
            elif "{" in segment or "}" in segment:
                raise ReferenceError(f"template variables must occupy a full segment: {segment!r}")
        if len(set(variables)) != len(variables):
            raise ReferenceError(f"template repeats variable(s): {self.template}")
        return tuple(variables)

    def format(self, values: Mapping[str, str]) -> SinnixRef:
        expected = set(self.variables)
        supplied = set(values)
        missing = expected - supplied
        extra = supplied - expected
        if missing or extra:
            details = []
            if missing:
                details.append(f"missing {sorted(missing)}")
            if extra:
                details.append(f"unexpected {sorted(extra)}")
            raise ReferenceError(f"cannot format {self.kind}: {', '.join(details)}")
        segments = tuple(
            values[segment[1:-1]]
            if segment.startswith("{") and segment.endswith("}")
            else segment
            for segment in self.segments
        )
        if any(not segment for segment in segments):
            raise ReferenceError(f"cannot format {self.kind}: empty resource segment")
        return SinnixRef.parse(f"sinnix://{'/'.join(quote(segment, safe='') for segment in segments)}")

    def match(self, reference: SinnixRef) -> dict[str, str] | None:
        if len(reference.segments) != len(self.segments):
            return None
        values: dict[str, str] = {}
        for expected, actual in zip(self.segments, reference.segments, strict=True):
            if expected.startswith("{") and expected.endswith("}"):
                values[expected[1:-1]] = actual
            elif expected != actual:
                return None
        return values
