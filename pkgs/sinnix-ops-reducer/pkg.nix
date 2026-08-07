{ lib, python3Packages }:

python3Packages.buildPythonApplication {
  pname = "sinnix-ops-reducer";
  version = "0.1.0";
  pyproject = true;
  src = ./.;
  build-system = [ python3Packages.setuptools ];
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
