{
  python3Packages,
  ...
}:
python3Packages.buildPythonPackage {
  pname = "sinnix-mcp";
  version = "0.1.0";
  pyproject = true;
  src = ./.;

  build-system = [ python3Packages.setuptools ];
  nativeCheckInputs = [ python3Packages.pytest ];

  checkPhase = ''
    runHook preCheck
    pytest
    runHook postCheck
  '';

  pythonImportsCheck = [ "sinnix_mcp" ];

  meta.description = "Canonical Sinnix MCP references, envelopes, and owner registration";
}
