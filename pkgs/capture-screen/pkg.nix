{
  lib,
  python3Packages,
}:
python3Packages.buildPythonApplication {
  pname = "sinnix-capture-screen";
  version = "0.1.0";
  pyproject = true;
  src = ./.;
  build-system = [ python3Packages.setuptools ];
  # No Python-level dependency on sinnix-capture-lib: the daemon shells out
  # to the `sinnix-capture` CLI binary (injected as --sinnix-capture-bin by
  # modules/services/capture-screen.nix), the same pattern
  # capture-input-dynamics uses -- not an in-process import.
  dependencies = [
    python3Packages.pillow
    python3Packages.numpy
  ];
  nativeCheckInputs = [ python3Packages.pytest ];
  checkPhase = ''
    runHook preCheck
    pytest -q
    runHook postCheck
  '';
  meta = {
    description = "Hyprland-event + idle-pause + 30s-floor triggered per-window screen frame capture (p-hash dedup, WebP q80)";
    mainProgram = "sinnix-capture-screen";
    license = lib.licenses.mit;
  };
}
