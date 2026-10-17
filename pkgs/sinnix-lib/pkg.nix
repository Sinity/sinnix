{
  python3Packages,
  lib,
}:
python3Packages.buildPythonPackage {
  pname = "sinnix-lib";
  version = "0.1.0";
  pyproject = true;
  src = lib.fileset.toSource {
    root = ./.;
    fileset = lib.fileset.unions [
      ./pyproject.toml
      ./sinnix_lib
    ];
  };
  doCheck = false;
  build-system = [ python3Packages.setuptools ];
  pythonImportsCheck = [
    "sinnix_lib"
    "sinnix_lib.atomic"
    "sinnix_lib.atomic_json"
    "sinnix_lib.files"
    "sinnix_lib.http"
    "sinnix_lib.ledger"
    "sinnix_lib.secrets"
    "sinnix_lib.lock"
    "sinnix_lib.mounts"
    "sinnix_lib.note_links"
    "sinnix_lib.notify"
    "sinnix_lib.paths"
    "sinnix_lib.phone_inbox"
    "sinnix_lib.procfs"
    "sinnix_lib.process"
    "sinnix_lib.spool"
    "sinnix_lib.systemd"
    "sinnix_lib.values"
    "sinnix_lib.layout"
    "sinnix_lib.judgments"
    "sinnix_lib.taxonomy"
    "sinnix_lib.catalog_paths"
  ];
}
