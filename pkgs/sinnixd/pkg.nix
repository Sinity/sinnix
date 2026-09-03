{
  python3Packages,
  sinnix-mcp,
  sinnix-lib,
  git,
  beads,
  worktrunk,
  pueue,
  ...
}:
python3Packages.buildPythonApplication {
  pname = "sinnixd";
  version = "0.1.0";
  pyproject = true;
  src = ./.;

  build-system = [ python3Packages.setuptools ];
  dependencies = [
    sinnix-mcp
    sinnix-lib
  ];
  nativeCheckInputs = [
    python3Packages.pytest
    git
    beads
    worktrunk
    pueue
  ];

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
