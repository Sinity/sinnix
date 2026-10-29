"""Exercise upstream EGL2 queue code with synthetic protocol failures and real Wayland."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path


def run(args, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, **kwargs)


def source_header(source: str) -> str:
    start = source.index("static struct wl_buffer *ShareDmaBuf(")
    body = source.index("{", start)
    depth = 1
    end = body + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    function = source[start:end]
    create = source[source.index("WlSwapChain *eplWlSwapChainCreate(") :]
    policy = create.split("    swapchain->prime = prime;", 1)[1].split(
        "    /*\n     * Start by creating the render buffer.", 1
    )[0]
    return (
        function
        + "\nstatic bool queue_policy(WlDisplayInstance *inst, WlSwapChain *swapchain, struct wl_surface *wsurf) {\n"
        + policy
        + "\nreturn true;\ndone: return false;\n}\n"
    )


def exports(library: Path) -> set[str]:
    return {
        line.split()[-1]
        for line in run(
            ["nm", "-D", "--defined-only", str(library)]
        ).stdout.splitlines()
    }


baseline, patched, fixture, real_fixture, output = map(Path, sys.argv[1:])
output.mkdir(exist_ok=True)
for name, source in (("baseline", baseline), ("patched", patched)):
    directory = Path(name)
    directory.mkdir()
    (directory / "queue-source.h").write_text(source_header(source.read_text()))
    binary = directory / "test"
    run(
        [
            "cc",
            "-std=gnu11",
            "-UNDEBUG",
            "-fsanitize=address",
            "-fno-omit-frame-pointer",
            "-I",
            str(directory),
            str(fixture),
            "-o",
            str(binary),
        ]
    )
    result = subprocess.run([str(binary.resolve())], text=True, capture_output=True)
    (output / f"{name}.stdout").write_text(result.stdout)
    (output / f"{name}.stderr").write_text(result.stderr)
    if name == "baseline":
        assert result.returncode == 1
        assert result.stderr == "explicit synchronization retained a private queue\n"
    else:
        assert result.returncode == 0, result.stderr

flags = run(["pkg-config", "--cflags", "--libs", "wayland-client"]).stdout.split()
run(
    [
        "cc",
        "-std=c11",
        "-UNDEBUG",
        "-fsanitize=address",
        "-fno-omit-frame-pointer",
        str(real_fixture),
        "-o",
        "wayland-release-test",
        *flags,
    ]
)
real = run([str(Path("wayland-release-test").resolve())])
(output / "wayland.stdout").write_text(real.stdout)

old_library = Path(os.environ["BASELINE_EGL"]) / "lib/libnvidia-egl-wayland2.so.1"
new_library = Path(os.environ["PATCHED_EGL"]) / "lib/libnvidia-egl-wayland2.so.1"
old_exports, new_exports = exports(old_library), exports(new_library)
assert old_exports == new_exports and "loadEGLExternalPlatform" in new_exports
soname = re.search(
    r"\(SONAME\).*\[(.*)\]", run(["readelf", "-d", str(new_library)]).stdout
)[1]
assert soname == "libnvidia-egl-wayland2.so.1"
files = json.loads(os.environ["EGL_PLATFORM_FILES"])
assert len(files) == 5
manifests = [json.loads(Path(path).read_text()) for path in files]
assert manifests[0]["ICD"]["library_path"] == str(new_library)
assert [Path(path).name for path in files[1:]] == [
    "10_nvidia_wayland.json",
    "15_nvidia_gbm.json",
    "20_nvidia_xcb.json",
    "20_nvidia_xlib.json",
]
for manifest in manifests:
    assert manifest["file_format_version"] == "1.0.0"
    assert Path(manifest["ICD"]["library_path"]).is_absolute()
    assert Path(manifest["ICD"]["library_path"]).is_file()
(output / "proof.json").write_text(
    json.dumps(
        {
            "baseline_failed_as_expected": True,
            "patched_queue_cases_passed": True,
            "real_null_listener_release_passed": True,
            "exports_unchanged": True,
            "soname": soname,
            "platform_count": len(files),
        },
        indent=2,
    )
    + "\n"
)
