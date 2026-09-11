{
  python3Packages,
  lib,
  sinnix-lib,
  ...
}:
python3Packages.buildPythonApplication {
  pname = "sinnix-observe";
  version = "0.1.0";
  pyproject = true;
  src = ./.;

  build-system = [ python3Packages.setuptools ];

  # sinnix-lib is the only import beyond the standard library: the guarded
  # subprocess wrapper and the lenient scalar reads every collector uses.
  # The tools themselves (systemctl, below, iostat) come from the host
  # environment rather than the package closure.
  dependencies = [ sinnix-lib ];

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
    "sinnix_observe.runtime_inventory"
    "sinnix_observe.sources.below"
    "sinnix_observe.sources.agent_gateway"
    "sinnix_observe.sources.chrome"
    "sinnix_observe.sources.polylogue"
    "sinnix_observe.sources.pressure"
    "sinnix_observe.sources.storage"
    "sinnix_observe.sources.systemd"
    "sinnix_observe.sources.xtask"
  ];

  meta = {
    description = "Sinnix workstation observability report";
    mainProgram = "sinnix-observe";
    license = lib.licenses.mit;
  };
}
