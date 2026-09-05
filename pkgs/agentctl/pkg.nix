{
  python3Packages,
  git,
  beads,
  worktrunk,
  pueue,
  ...
}:
python3Packages.buildPythonApplication {
  pname = "agentctl";
  version = "0.1.0";
  pyproject = true;
  src = ./.;

  build-system = [ python3Packages.setuptools ];
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

  pythonImportsCheck = [ "agentctl" ];

  meta = {
    description = "agentctl: jobs over pueue, lanes over worktrunk, gh and bd";
    mainProgram = "agentctl";
  };
}
