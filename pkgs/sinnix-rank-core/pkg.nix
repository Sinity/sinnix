{
  python3Packages,
  lib,
}:
python3Packages.buildPythonPackage {
  pname = "sinnix-rank-core";
  version = "0.1.0";
  pyproject = true;
  src = lib.cleanSource ./.;
  build-system = [ python3Packages.setuptools ];
  nativeCheckInputs = [ python3Packages.pytestCheckHook ];
  pythonImportsCheck = [
    "rank_core"
    "rank_core.store"
    "rank_core.fit"
    "rank_core.stopping"
    "rank_core.selection"
    "rank_core.draw"
  ];
}
