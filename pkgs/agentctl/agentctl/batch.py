"""Batches: several workers on one base commit, one landing, one acceptance record.

The verbs live in `start` (start, result, resume), `landing` (land) and
`operator_view` (status); the manifest, its refusals and the run record in
`manifest`. This module is the import path callers use.
"""

from __future__ import annotations

from .landing import land
from .manifest import BatchError, BatchRefusal
from .operator_view import status
from .start import result, resume, start

__all__ = [
    "BatchError",
    "BatchRefusal",
    "land",
    "result",
    "resume",
    "start",
    "status",
]
