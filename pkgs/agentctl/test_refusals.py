"""Every refusal code is declared once and documented once."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from agentctl import manifest

PACKAGE = Path(manifest.__file__).parent
DOC = PACKAGE.parents[2] / "docs" / "agentctl.md"


def raised_codes() -> set[str]:
    codes: set[str] = set()
    for path in PACKAGE.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "BatchRefusal"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                codes.add(str(node.args[0].value))
    return codes


def test_every_raised_code_is_in_the_table() -> None:
    raised = raised_codes()
    assert raised, "no BatchRefusal call found; the scan is broken"
    assert raised <= set(manifest.REFUSALS)
    assert set(manifest.REFUSALS) <= raised, "a documented code is never raised"


def test_an_undeclared_code_cannot_be_raised() -> None:
    with pytest.raises(ValueError, match="unknown refusal code"):
        manifest.BatchRefusal("nope", "x")


def test_the_documentation_lists_every_code() -> None:
    if not DOC.is_file():
        pytest.skip(f"{DOC} is not part of this source tree")
    text = DOC.read_text()
    section = text.split("### Refusals", 1)
    assert len(section) == 2, "docs/agentctl.md has no Refusals section"
    documented = set(re.findall(r"^\| `([a-z_]+)`", section[1], flags=re.MULTILINE))
    assert documented == set(manifest.REFUSALS)
