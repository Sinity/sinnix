{ lib, python3Packages }:

python3Packages.buildPythonApplication {
  pname = "sinnix-capture";
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
    description = "Shared sinnix-capture-v1 JSONL envelope writer and sidecar-index query surface for capture lanes";
    mainProgram = "sinnix-capture";
    license = lib.licenses.mit;
  };
}
