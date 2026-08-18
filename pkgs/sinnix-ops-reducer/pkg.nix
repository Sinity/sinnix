{
  lib,
  python3Packages,
  sinnix-lib,
  # terminals.py shells out to these by bare name (`kitty @ ...`, `aha ...`);
  # a buildPythonApplication has no writeShellApplication runtimeInputs
  # wrapper of its own to carry them, so they go on the built console_script's
  # PATH directly -- same pattern as sinnix-phone-dispatcher's
  # steerPackage/scorePackage (pkgs/sinnix-phone-dispatcher/pkg.nix).
  kittyPackage,
  ahaPackage,
}:

python3Packages.buildPythonApplication {
  pname = "sinnix-ops-reducer";
  version = "0.1.0";
  pyproject = true;
  src = ./.;
  build-system = [ python3Packages.setuptools ];
  # Sinnix's shared primitives (atomic state, ledgers, locks, desktop
  # notification, batched systemd probes) the health sweep and the action
  # receipts are written against, rather than private copies of each.
  dependencies = [ sinnix-lib ];
  makeWrapperArgs = [
    "--prefix"
    "PATH"
    ":"
    (lib.makeBinPath [
      kittyPackage
      ahaPackage
    ])
  ];
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
