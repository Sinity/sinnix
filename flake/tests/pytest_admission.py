"""Drive patched Polylogue pytest admission (sinnix-do66).

Anti-vacuity: restoring ``max(1, ...)`` in ``width_within`` /
``memory_bounded_worker_cap``, or launching from ``_run_held`` /
``_run_launch`` when the cgroup cannot hold one worker, fails these tests.
"""

from __future__ import annotations

import json
import os
import unittest
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict

from devtools import pytest_slot as slot
from devtools.worker_memory import (
    CONTROLLER_PEAK_MIB,
    CORPUS_MAX_WORKERS,
    MEMORY_HEADROOM_FRACTION,
    WORKER_PEAK_MIB,
    memory_bounded_worker_cap,
    resize_worker_argument,
    width_within,
)


class CgroupPaths(TypedDict):
    process_cgroup: Path
    cgroup_root: Path


MIB = 1024 * 1024
SLOT_531_CGROUP_MIB = 46
AMPLE_HOST_MIB = 14302


def _one_worker_floor_mib() -> float:
    return (CONTROLLER_PEAK_MIB + WORKER_PEAK_MIB) / (1.0 - MEMORY_HEADROOM_FRACTION)


def _meminfo(root: Path, available_mib: int) -> Path:
    path = root / "meminfo"
    path.write_text(
        f"MemTotal:       32689696 kB\nMemFree:         1000000 kB\nMemAvailable:   {available_mib * 1024} kB\n",
        encoding="utf-8",
    )
    return path


def _cgroup(root: Path, levels: Sequence[tuple[str, Mapping[str, str]]]) -> CgroupPaths:
    cgroup_root = root / "cgroup-root"
    cgroup_root.mkdir()
    directory = cgroup_root
    parts: list[str] = []
    for name, files in levels:
        parts.append(name)
        directory = directory / name
        directory.mkdir(parents=True, exist_ok=True)
        for filename, content in files.items():
            (directory / filename).write_text(content, encoding="utf-8")
    process_cgroup = root / "self-cgroup"
    process_cgroup.write_text("0::/" + "/".join(parts) + "\n", encoding="utf-8")
    return CgroupPaths(process_cgroup=process_cgroup, cgroup_root=cgroup_root)


def _bytes(mib: int) -> str:
    return str(mib * MIB)


def _job_cgroup(root: Path, *, available_mib: int, current_mib: int = 0) -> CgroupPaths:
    return _cgroup(
        root,
        [
            (
                "job.slice",
                {
                    "memory.max": _bytes(available_mib + current_mib),
                    "memory.high": _bytes(available_mib + current_mib),
                    "memory.current": _bytes(current_mib),
                },
            )
        ],
    )


def _bind_resize(meminfo: Path, paths: CgroupPaths):
    def bound(argv: list[str], **_kwargs: object) -> tuple[list[str], dict[str, Any] | None]:
        return resize_worker_argument(
            argv,
            meminfo=meminfo,
            process_cgroup=paths["process_cgroup"],
            cgroup_root=paths["cgroup_root"],
        )

    return bound


class PytestAdmissionTests(unittest.TestCase):
    def test_a_46_mib_cgroup_is_not_ready_even_with_ample_host_memory(self) -> None:
        root = Path(os.environ["TMPDIR"]) / "slot-531"
        root.mkdir()
        workers, basis = memory_bounded_worker_cap(
            requested=8,
            meminfo=_meminfo(root, AMPLE_HOST_MIB),
            **_job_cgroup(root, available_mib=SLOT_531_CGROUP_MIB),
        )
        self.assertEqual(workers, 0)
        self.assertEqual(basis["admission"], "resource_not_ready")
        self.assertEqual(basis["cgroup_available_mib"], SLOT_531_CGROUP_MIB)
        self.assertEqual(basis["host_available_mib"], AMPLE_HOST_MIB)

    def test_controller_plus_one_worker_headroom_admits_exactly_one(self) -> None:
        floor = _one_worker_floor_mib()
        self.assertEqual(width_within(floor), 1)
        self.assertEqual(width_within(floor - 1), 0)
        root = Path(os.environ["TMPDIR"]) / "one-worker"
        root.mkdir()
        workers, basis = memory_bounded_worker_cap(
            requested=8,
            meminfo=_meminfo(root, AMPLE_HOST_MIB),
            **_job_cgroup(root, available_mib=int(floor + 1)),
        )
        self.assertEqual(workers, 1)
        self.assertEqual(basis["admission"], "admitted")

    def test_a_roomy_budget_keeps_narrowed_width(self) -> None:
        root = Path(os.environ["TMPDIR"]) / "roomy"
        root.mkdir()
        workers, basis = memory_bounded_worker_cap(
            requested=CORPUS_MAX_WORKERS,
            meminfo=_meminfo(root, 28000),
            **_job_cgroup(root, available_mib=6 * 1024),
        )
        self.assertGreaterEqual(workers, 1)
        self.assertEqual(basis["admission"], "admitted")
        self.assertEqual(workers, min(CORPUS_MAX_WORKERS, width_within(6 * 1024)))

    def test_held_launch_defers_before_popen_on_a_46_mib_cgroup(self) -> None:
        root = Path(os.environ["TMPDIR"]) / "held"
        root.mkdir()
        meminfo = _meminfo(root, AMPLE_HOST_MIB)
        paths = _job_cgroup(root, available_mib=SLOT_531_CGROUP_MIB)
        original_resize = slot.resize_worker_argument
        original_popen = slot.subprocess.Popen

        def boom(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("held path restored unconditional one-worker admission")

        slot.resize_worker_argument = _bind_resize(meminfo, paths)
        slot.subprocess.Popen = boom
        try:
            returncode, receipt = slot._run_held(
                ["python", "-m", "pytest", "-n", "8", "tests"],
                cwd=str(root),
                env={"PATH": os.environ.get("PATH", "")},
                stdout=None,
                on_exit=lambda: None,
            )
        finally:
            slot.resize_worker_argument = original_resize
            slot.subprocess.Popen = original_popen
        self.assertEqual(returncode, slot.EX_TEMPFAIL)
        self.assertEqual(receipt["status"], slot.RESOURCE_NOT_READY)
        self.assertEqual(receipt["sizing"]["workers"], 0)
        self.assertEqual(receipt["sizing"]["admission"], "resource_not_ready")

    def test_queued_launch_defers_before_popen_on_a_46_mib_cgroup(self) -> None:
        root = Path(os.environ["TMPDIR"]) / "queued"
        root.mkdir()
        meminfo = _meminfo(root, AMPLE_HOST_MIB)
        paths = _job_cgroup(root, available_mib=SLOT_531_CGROUP_MIB)
        launch = root / "launch.json"
        log = root / "run.log"
        launch.write_text(
            json.dumps(
                {
                    "argv": ["python", "-m", "pytest", "-n", "8", "tests"],
                    "environment": {},
                    "working_directory": str(root),
                    "log_path": str(log),
                }
            ),
            encoding="utf-8",
        )
        original_resize = slot.resize_worker_argument
        original_popen = slot.subprocess.Popen

        def boom(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("queued path restored unconditional one-worker admission")

        slot.resize_worker_argument = _bind_resize(meminfo, paths)
        slot.subprocess.Popen = boom
        try:
            returncode = slot._run_launch(launch)
        finally:
            slot.resize_worker_argument = original_resize
            slot.subprocess.Popen = original_popen
        self.assertEqual(returncode, slot.EX_TEMPFAIL)
        result = json.loads((root / "run.result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], slot.RESOURCE_NOT_READY)
        self.assertEqual(result["sizing"]["workers"], 0)


if __name__ == "__main__":
    unittest.main()
