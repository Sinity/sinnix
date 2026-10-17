{
  lib,
  python3Packages,
  sinnix-lib,
}:

python3Packages.buildPythonApplication {
  pname = "sinnix-capture";
  version = "0.1.0";
  pyproject = true;
  src = lib.fileset.toSource {
    root = ./.;
    fileset = lib.fileset.unions [
      ./pyproject.toml
      ./sinnix_capture
    ];
  };
  doCheck = false;
  build-system = [ python3Packages.setuptools ];
  dependencies = [ sinnix-lib ];
  pythonImportsCheck = [ "sinnix_capture" ];

  meta = {
    description = "Shared sinnix-capture-v1 JSONL envelope writer and sidecar-index query surface for capture lanes";
    mainProgram = "sinnix-capture";
    license = lib.licenses.mit;
  };
}
