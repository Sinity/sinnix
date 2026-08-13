{ lib, python3Packages }:

python3Packages.buildPythonApplication {
  pname = "sinnix-cockpit";
  version = "0.1.0";
  pyproject = true;
  src = ./.;
  build-system = [ python3Packages.setuptools ];
  dependencies = [
    python3Packages.fastapi
    python3Packages.uvicorn
  ];
  nativeCheckInputs = [
    python3Packages.pytest
    python3Packages.httpx # required by fastapi.testclient.TestClient
  ];
  checkPhase = ''
    runHook preCheck
    pytest -q
    runHook postCheck
  '';
  meta = {
    description = "Read-only steering cockpit (sinnix-jfiy.1): today's intentions, calibration, activity menu";
    mainProgram = "sinnix-cockpit";
    license = lib.licenses.mit;
  };
}
