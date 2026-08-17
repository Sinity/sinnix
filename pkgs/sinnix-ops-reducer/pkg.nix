{
  lib,
  python3Packages,
  sinnix-lib,
}:

python3Packages.buildPythonApplication {
  pname = "sinnix-ops-reducer";
  version = "0.1.0";
  pyproject = true;
  src = ./.;
  build-system = [ python3Packages.setuptools ];
  # The estate's shared primitives (atomic state, ledgers, locks, desktop
  # notification, batched systemd probes) the health sweep and the action
  # receipts are written against, rather than private copies of each.
  dependencies = [ sinnix-lib ];
  nativeCheckInputs = [ python3Packages.pytest ];
  checkPhase = ''
    runHook preCheck
    pytest -q
    runHook postCheck
  '';
  meta = {
    description = "Current-state reducer and bounded action contract for Sinnix operator surfaces";
    mainProgram = "sinnix-ops-reducer";
    license = lib.licenses.mit;
  };
}
