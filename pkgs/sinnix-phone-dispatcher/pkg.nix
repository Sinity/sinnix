{
  lib,
  python3Packages,
  sinnix-capture-lib,
  sinnix-lib,
  # sinnix-score, shelled out to (not imported) by
  # sinnix_phone_dispatcher.external. A buildPythonApplication has no
  # script-registry wrapper, so it is put on the built console_script's PATH
  # explicitly below.
  scorePackage,
}:

python3Packages.buildPythonApplication {
  pname = "sinnix-phone-dispatcher";
  version = "0.1.0";
  pyproject = true;
  src = lib.fileset.toSource {
    root = ./.;
    fileset = lib.fileset.unions [
      ./pyproject.toml
      ./sinnix_phone_dispatcher
    ];
  };
  doCheck = false;
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
    (lib.makeBinPath [ scorePackage ])
  ];
  pythonImportsCheck = [ "sinnix_phone_dispatcher" ];

  meta = {
    description = "Prime's phone transport, retained-request dispatcher, and telemetry receiver";
    mainProgram = "sinnix-phone-dispatcher";
    license = lib.licenses.mit;
  };
}
