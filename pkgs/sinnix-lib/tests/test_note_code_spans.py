"""Inline code scanning is bounded and uses complete delimiter runs."""

import os
import subprocess
import sys

import pytest
from sinnix_lib.note_links import prose_mask


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("before `one` after", "before       after"),
        ("`outer `` inner` tail", "                 tail"),
        ("``one ` two`` after", "              after"),
        ("``x```y", "``x```y"),
        ("`unmatched ``code`` tail", "`unmatched          tail"),
        ("prefix ``` missing", "prefix ``` missing"),
        ("`line\nnext` tail", "     \n      tail"),
        ("prefix `````x````` suffix", "prefix             suffix"),
    ],
)
def test_code_spans_use_equal_maximal_backtick_runs(text, expected):
    result = prose_mask(text)
    assert len(result) == len(text)
    assert result == expected


def test_long_unmatched_inline_delimiter_finishes_without_backtracking():
    program = "from sinnix_lib.note_links import prose_mask; text='x'+'`'*12000+'x'; assert prose_mask(text)==text"
    result = subprocess.run(
        [sys.executable, "-c", program],
        env={"PATH": "/nonexistent", "PYTHONPATH": os.pathsep.join(sys.path)},
        capture_output=True,
        text=True,
        timeout=3,
    )
    assert result.returncode == 0, result.stderr
