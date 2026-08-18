{
  lib,
  python3Packages,
  sinnix-capture-lib,
  sinnix-lib,
  # sinnix-steer/sinnix-score, shelled out to (not imported) by
  # sinnix_phone_dispatcher.external -- the retired scripts/ frontmatter
  # named them as `runtimeInputs: coreutils @sinnix-steer @sinnix-score`,
  # which a script-registry writeShellApplication wrapper turned into PATH
  # entries. A buildPythonApplication has no such wrapper of its own, so
  # they are put on the built console_script's PATH explicitly below.
  steerPackage,
  scorePackage,
}:

python3Packages.buildPythonApplication {
  pname = "sinnix-phone-dispatcher";
  version = "0.1.0";
  pyproject = true;
  src = ./.;
  build-system = [ python3Packages.setuptools ];
  # sinnix-capture-lib: the CaptureWriter/build_envelope the phone-stream
  # receiver appends through -- this package is their canonical origin, no
  # longer a private port (see receiver.py). sinnix-lib: the shared
  # atomic-state/ledger/lock primitives, depended on for architecture
  # consistency with the other sinnix Python packages; this package's own
  # JSON writes keep their existing (non-compact) on-disk format rather than
  # adopting sinnix_lib.atomic_json's sort_keys+compact-separator shape (see
  # state.py) -- the phone app and the drain already parse these files as
  # written, and changing their bytes was out of scope for this move.
  dependencies = [
    sinnix-capture-lib
    sinnix-lib
  ];
  makeWrapperArgs = [
    "--prefix"
    "PATH"
    ":"
    (lib.makeBinPath [
      steerPackage
      scorePackage
    ])
  ];
  nativeCheckInputs = [ python3Packages.pytest ];
  checkPhase = ''
    runHook preCheck
    pytest -q
    runHook postCheck
  '';
  meta = {
    description = "Prime's half of the phone's dual transport -- the live JSON API, the drained-intent dispatcher, and the always-on telemetry receiver";
    mainProgram = "sinnix-phone-dispatcher";
    license = lib.licenses.mit;
  };
}
