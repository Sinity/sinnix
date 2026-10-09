"""Exercise the installed tools against independent synthetic expectations."""

import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def rea(*args):
    result = subprocess.run(
        ["rea", *map(str, args), "--json"],
        text=True,
        capture_output=True,
        timeout=240,
    )
    if result.returncode:
        raise RuntimeError(f"REA {args}: {result.stdout}\n{result.stderr}")
    return json.loads(result.stdout)


with tempfile.TemporaryDirectory(prefix="reverse-engineering-", dir=os.environ["TMPDIR"]) as temp:
    root = Path(temp)
    doctor = rea("doctor", "--provider", "ghidra")
    assert doctor["healthy"], doctor
    payload = b"Synthetic firmware extraction fixture.\n" * 100
    firmware = root / "fixture.gz"
    firmware.write_bytes(gzip.compress(payload, mtime=0))
    before = hashlib.sha256(firmware.read_bytes()).hexdigest()
    regions = rea("inspect-firmware-regions", firmware)
    assert "gzip" in json.dumps(regions).lower(), regions
    output = root / "extracted"
    rea("extract-firmware", firmware, output)
    files = [p for p in output.rglob("*") if p.is_file()]
    assert any(p.read_bytes() == payload for p in files), files
    assert hashlib.sha256(firmware.read_bytes()).hexdigest() == before
    source = root / "fixture.c"
    source.write_text(
        "__attribute__((noinline)) int fixture_transform(int x) { return x * 7 + 13; }\n"
        "int main(int argc, char **argv) { return fixture_transform(argc); }\n"
    )
    binary = root / "fixture"
    subprocess.run(["cc", "-O0", "-g", "-o", str(binary), str(source)], check=True)
    original = hashlib.sha256(binary.read_bytes()).hexdigest()
    code = rea("decompile", binary, "fixture_transform", "--provider", "ghidra")
    rendered = json.dumps(code)
    assert "fixture_transform" in rendered and "13" in rendered, code
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == original
    print("PASS: Ghidra readiness, gzip inspection/extraction parity, native decompilation, unchanged sources")
