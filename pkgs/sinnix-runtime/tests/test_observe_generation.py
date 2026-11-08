from pathlib import Path

from sinnix_runtime.observe.sources.generation import collect_system_generation


def _generation(root: Path, name: str, kernel: str) -> Path:
    gen = root / name
    gen.mkdir()
    target = root / kernel
    target.write_text(kernel)
    (gen / "kernel").symlink_to(target)
    (gen / "initrd").symlink_to(target)
    return gen


def test_same_boot_parts_need_no_reboot(tmp_path: Path) -> None:
    booted = _generation(tmp_path, "a", "k1")
    current = _generation(tmp_path, "b", "k1")
    report = collect_system_generation(booted, current)
    assert report["status"] == "healthy"
    assert report["boot_parts_changed"] == []


def test_changed_kernel_requires_reboot(tmp_path: Path) -> None:
    booted = _generation(tmp_path, "a", "k1")
    current = _generation(tmp_path, "b", "k2")
    report = collect_system_generation(booted, current)
    assert report["status"] == "reboot_required"
    assert report["boot_parts_changed"] == ["kernel", "initrd"]


def test_missing_generation_is_unavailable(tmp_path: Path) -> None:
    report = collect_system_generation(tmp_path / "absent", tmp_path / "absent")
    assert report["available"] is False
