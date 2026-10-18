{
  lib,
  python3Packages,
  sinnix-lib,
  nodejs,
}:

python3Packages.buildPythonApplication {
  pname = "sinnix-hub-server";
  version = "0.1.0";
  pyproject = true;
  src = ./.;
  build-system = [ python3Packages.setuptools ];
  # Sinnix's shared primitives (atomic state, ledgers, locks, desktop
  # notification, batched systemd probes) the health sweep and the action
  # receipts are written against, rather than private copies of each.
  dependencies = [ sinnix-lib ];
  nativeCheckInputs = [ python3Packages.pytest nodejs ];
  SINNIX_CAPABILITIES_WRAPPER = ../../scripts/sinnix-capabilities;
  checkPhase = ''
    runHook preCheck
    pytest -q
    runHook postCheck
  '';
  meta = {
    description = "Current-state reducer and bounded action contract for Sinnix operator surfaces";
    mainProgram = "sinnix-hub-server";
    license = lib.licenses.mit;
  };
}
