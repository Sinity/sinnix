{ python3Packages, lib, ... }:
python3Packages.buildPythonApplication {
  pname = "sinnix-observe-py";
  version = "0.1.0";
  pyproject = true;
  src = ./.;

  build-system = [ python3Packages.setuptools ];

  # Pure-stdlib at runtime; collectors shell out to systemctl/below/etc., which
  # are provided by the host environment rather than the package closure.
  dependencies = [ ];

  nativeCheckInputs = [ python3Packages.pytest ];

  checkPhase = ''
    runHook preCheck
    pytest tests/
    runHook postCheck
  '';

  # No tests/test pollution at runtime — package only the application code.
  pythonImportsCheck = [
    "sinnix_observe"
    "sinnix_observe.cli"
    "sinnix_observe.joins"
    "sinnix_observe.render"
    "sinnix_observe.sources.below"
    "sinnix_observe.sources.chrome"
    "sinnix_observe.sources.polylogue"
    "sinnix_observe.sources.pressure"
    "sinnix_observe.sources.storage"
    "sinnix_observe.sources.systemd"
    "sinnix_observe.sources.xtask"
  ];

  meta = {
    description = "Sinnix workstation observability report (packaged split of scripts/sinnix-observe)";
    mainProgram = "sinnix-observe-py";
    license = lib.licenses.mit;
  };
}
