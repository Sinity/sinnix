{
  lib,
  python3Packages,
  sinnix-lib,
}:
python3Packages.buildPythonApplication {
  pname = "machine-telemetry";
  version = "0.1.0";
  pyproject = true;
  src = lib.fileset.toSource {
    root = ./.;
    fileset = lib.fileset.unions [
      ./pyproject.toml
      ./machine_telemetry
    ];
  };
  doCheck = false;

  build-system = [ python3Packages.setuptools ];
  dependencies = [
    python3Packages.nvidia-ml-py
    sinnix-lib
  ];
  pythonImportsCheck = [
    "machine_telemetry.collector"
    "machine_telemetry.rotation"
  ];

  meta = {
    description = "Canonical host machine telemetry collector";
    mainProgram = "machine-telemetry";
    license = lib.licenses.mit;
  };
}
