{
  lib,
  python3Packages,
  sinnix-capture-lib,
}:
python3Packages.buildPythonApplication {
  pname = "sinnix-audio-capture";
  version = "0.1.0";
  pyproject = true;
  src = ./.;
  build-system = [ python3Packages.setuptools ];
  # torch/torchaudio (pulled in transitively by silero-vad) are only ever
  # imported inside sinnix_audio_capture.indexer's model-loading functions,
  # deferred the same way sinnix-capture-a11y defers pyatspi/gi -- the rest
  # of the package (segment rotation, default-target resolution, topology
  # parsing, pause/gap records) stays pure and importable without them.
  dependencies = [
    python3Packages.silero-vad
    sinnix-capture-lib
  ];
  nativeCheckInputs = [ python3Packages.pytest ];
  checkPhase = ''
    runHook preCheck
    pytest -q
    runHook postCheck
  '';
  meta = {
    description = "Always-on PipeWire audio capture (every source + sink-monitor): Opus archive tier, pw-mon topology stream, Silero VAD index-only lane, pause/gap CLI";
    mainProgram = "sinnix-audio-capture";
    license = lib.licenses.mit;
  };
}
