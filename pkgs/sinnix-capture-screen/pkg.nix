{
  lib,
  python3Packages,
  sinnix-lib,
}:
python3Packages.buildPythonApplication {
  pname = "sinnix-capture-screen";
  version = "0.1.0";
  pyproject = true;
  src = ./.;
  build-system = [ python3Packages.setuptools ];
  # Envelope publication remains a CLI boundary, while frame bytes use the
  # shared atomic publisher before their raw reference becomes observable.
  dependencies = [
    python3Packages.pillow
    python3Packages.numpy
    sinnix-lib
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
