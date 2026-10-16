"""Preserve Kokoro's vendor entrypoint while admitting requests before dispatch."""

import os
import sys
from pathlib import Path


def listener_ports():
    from sinnix_ai_browser_boundary import BrowserBoundary

    ports = {int(value) for value in os.environ["SINNIX_KOKORO_PORTS"].split(",")}
    BrowserBoundary(None, allowed_ports=ports)
    return ports


def startup_script(source):
    target = "api.src.main:app"
    if source.count(target) != 1:
        raise ValueError("unsupported Kokoro entrypoint: expected one app target")
    return source.replace(target, "sinnix_kokoro:create_app --factory")


def create_app():
    ports = listener_ports()
    from api.src.main import app
    from sinnix_ai_browser_boundary import admit_fastapi

    return admit_fastapi(app, allowed_ports=ports)


def main():
    listener_ports()
    script = startup_script(Path("/app/entrypoint.sh").read_text())
    module_dir = str(Path(__file__).resolve().parent)
    previous = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = module_dir + (os.pathsep + previous if previous else "")
    os.chdir("/app")
    os.execv("/bin/bash", ["bash", "-c", script, "entrypoint.sh", *sys.argv[1:]])


if __name__ == "__main__":
    main()
