{
  lib,
  python3Packages,
}:
python3Packages.buildPythonApplication {
  pname = "sinnix-deslop";
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
    description = "Regex-based LLM-slop phrase stripper (sinnix-uou) -- output cleanup for generation lanes";
    mainProgram = "sinnix-deslop";
    license = lib.licenses.mit;
  };
}
