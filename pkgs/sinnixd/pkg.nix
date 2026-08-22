{
  python3Packages,
  sinnix-mcp,
  ...
}:
python3Packages.buildPythonApplication {
  pname = "sinnixd";
  version = "0.1.0";
  pyproject = true;
  src = ./.;

  build-system = [ python3Packages.setuptools ];
  dependencies = [ sinnix-mcp ];
  nativeCheckInputs = [ python3Packages.pytest ];

  checkPhase = ''
    runHook preCheck
    pytest
    runHook postCheck
  '';

  pythonImportsCheck = [ "sinnixd" ];

  meta = {
    description = "Sinnix local runtime daemon and agentctl client";
    mainProgram = "agentctl";
  };
}
