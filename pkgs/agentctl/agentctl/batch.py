"""Batches: several workers on one base commit, one landing, one acceptance record.

The verbs live in `start` (start, result, resume), `landing` (land, queue,
abandon, clean) and `operator_view` (status); the manifest, its refusals, its
lookups and the run record in `manifest`. This module is the import path
callers use.
"""

from __future__ import annotations

from .landing import abandon, clean, land, queue
from .manifest import BatchError, BatchRefusal, list_runs, load, resolve_run_id
from .operator_view import status
from .start import correct_scope, result, resume, start

__all__ = [
    "BatchError",
    "BatchRefusal",
    "abandon",
    "clean",
    "correct_scope",
    "land",
    "list_runs",
    "load",
    "queue",
    "resolve_run_id",
    "result",
    "resume",
    "start",
    "status",
]
