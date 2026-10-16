"""Launch the pinned TTS app with admission outside its body-reading middleware."""

import os
import runpy
import shlex
import sys
from pathlib import Path


def listener_ports():
    ports = {int(value) for value in os.environ["SINNIX_TTS_PORTS"].split(",")}
    if not ports or any(not 1 <= port <= 65535 for port in ports):
        raise ValueError("invalid TTS listener ports")
    return ports


def startup_script(source, launcher):
    # Keep the vendor environment, voice acquisition and preload arguments.
    # An incompatible image must fail rather than silently skip admission.
    command = "python speech.py "
    if source.count(command) != 1:
        raise ValueError("unsupported TTS startup: expected one speech.py launch")
    return source.replace(command, f"exec python {shlex.quote(str(launcher))} serve ")


def install(openedai, ports):
    from sinnix_ai_browser_boundary import BrowserBoundary
    from sinnix_fastapi_admission import admit_fastapi

    original = openedai.OpenAIStub
    # Validate configuration before constructing any vendor/model state.
    BrowserBoundary(None, allowed_ports=ports)

    class AdmittedOpenAIStub(original):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            # Added last so this surrounds the vendor logging middleware too.
            admit_fastapi(self, allowed_ports=ports, allow_credentials=True)

    openedai.OpenAIStub = AdmittedOpenAIStub


def main():
    ports = listener_ports()
    mode, *arguments = sys.argv[1:]
    if mode == "start":
        startup = Path(os.environ.get("SINNIX_TTS_STARTUP", "/app/startup.sh"))
        script = startup_script(startup.read_text(), Path(__file__).resolve())
        os.chdir("/app")
        os.execv("/bin/bash", ["bash", "-c", script, startup.name, *arguments])
    elif mode == "serve":
        sys.path.insert(0, "/app")
        import openedai

        install(openedai, ports)
        sys.argv = ["/app/speech.py", *arguments]
        runpy.run_path("/app/speech.py", run_name="__main__")
    else:
        raise ValueError("expected start or serve")


if __name__ == "__main__":
    main()
