"""Run the host's actual policy script against a synthetic sysfs layout."""

from pathlib import Path
import subprocess
import sys
import tempfile


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    sysfs = root / "sys"
    filesystem = sysfs / "fs/btrfs/43701cf7-7880-4e0c-9725-b6e12d91898a"
    target = sysfs / "class/bdi/btrfs-97"
    raw = sysfs / "class/bdi/259:0"
    desktop = sysfs / "class/bdi/btrfs-12"
    for bdi in (target, raw, desktop):
        bdi.mkdir(parents=True)
        (bdi / "max_ratio").write_text("100\n")
        (bdi / "strict_limit").write_text("0\n")
    filesystem.mkdir(parents=True)
    (filesystem / "bdi").symlink_to(target)
    # Rewrite only the sysfs root, retaining the production UUID lookup and
    # writes. BDI numbering is deliberately unlike this boot's btrfs-3.
    script = root / "policy.sh"
    script.write_text(Path(sys.argv[1]).read_text().replace("/sys/", f"{sysfs}/"))
    for _ in range(2):
        subprocess.run(["bash", "-eu", script], check=True)
        assert (target / "max_ratio").read_text() == "25\n"
        assert (target / "strict_limit").read_text() == "1\n"
        for other in (raw, desktop):
            assert (other / "max_ratio").read_text() == "100\n"
            assert (other / "strict_limit").read_text() == "0\n"
    (filesystem / "bdi").unlink()
    missing = subprocess.run(["bash", "-eu", script], capture_output=True)
    assert missing.returncode != 0, "A missing mounted filesystem must fail visibly"
