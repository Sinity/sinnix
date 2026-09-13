{
  lib,
  python3Packages,
  coreutils,
  zstd,
  sinnix-lib,
}:
python3Packages.buildPythonApplication {
  pname = "machine-telemetry";
  version = "0.1.0";
  pyproject = true;
  src = ./.;

  build-system = [ python3Packages.setuptools ];
  dependencies = [
    python3Packages.nvidia-ml-py
    sinnix-lib
  ];
  nativeCheckInputs = [
    python3Packages.pytest
    coreutils
    zstd
  ];

  checkPhase = ''
    runHook preCheck
    pytest -q tests/test_collector_process_memory.py
    runHook postCheck
  '';

  pythonImportsCheck = [ "machine_telemetry.collector" ];

  meta = {
    description = "Canonical host machine telemetry collector";
    mainProgram = "machine-telemetry";
    license = lib.licenses.mit;
  };
}
