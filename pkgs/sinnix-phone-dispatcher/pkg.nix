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
  # Shared capture and state helpers keep phone ingress consistent with other
  # producers; JSON writes retain the format the app and drain parse.
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
