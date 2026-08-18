{
  python3Packages,
  lib,
}:
python3Packages.buildPythonPackage {
  pname = "sinnix-lib";
  version = "0.1.0";
  pyproject = true;
  src = lib.cleanSource ./.;
  build-system = [ python3Packages.setuptools ];
  nativeCheckInputs = [ python3Packages.pytestCheckHook ];
  pythonImportsCheck = [
    "sinnix_lib"
    "sinnix_lib.atomic_json"
    "sinnix_lib.ledger"
    "sinnix_lib.lock"
    "sinnix_lib.notify"
    "sinnix_lib.paths"
    "sinnix_lib.phone_inbox"
    "sinnix_lib.spool"
    "sinnix_lib.systemd"
  ];
}
