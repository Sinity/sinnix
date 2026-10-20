{
  lib,
  python3Packages,
  sinnix-lib,
}:
python3Packages.buildPythonPackage {
  pname = "sinnix-runtime";
  version = "0.1.0";
  pyproject = true;
  src = lib.fileset.toSource {
    root = ./.;
    fileset = lib.fileset.unions [
      ./pyproject.toml
      ./sinnix_runtime
    ];
  };
  build-system = [ python3Packages.setuptools ];
  dependencies = [ sinnix-lib ];
  doCheck = false;
  pythonImportsCheck = [
    "sinnix_runtime.client"
    "sinnix_runtime.actions"
    "sinnix_runtime.observe.cli"
    "sinnix_runtime.snapshot"
  ];
}
