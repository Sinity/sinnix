{
  python3Packages,
  lib,
  fetchPypi,
  git,
  ripgrep,
  fd,
  gnused,
  gnutar,
  gzip,
  coreutils,
  ...
}:
let
  mkPinnedPythonPackage =
    {
      pname,
      version,
      hash,
      dependencies,
      build-system,
      pythonRelaxDeps ? [ ],
    }:
    python3Packages.buildPythonPackage {
      inherit
        pname
        version
        dependencies
        build-system
        pythonRelaxDeps
        ;
      pyproject = true;
      src = fetchPypi { inherit pname version hash; };
      env.UV_DYNAMIC_VERSIONING_BYPASS = version;
      doCheck = false;
    };

  httpcore2 = mkPinnedPythonPackage {
    pname = "httpcore2";
    version = "2.9.1";
    hash = "sha256-TYrL+LMG9IydYEZZH9W6QDfRsbEADRQPwsPqsemgwOI=";
    dependencies = with python3Packages; [
      h11
      truststore
    ];
    build-system = with python3Packages; [
      hatch-fancy-pypi-readme
      hatchling
      uv-dynamic-versioning
    ];
  };

  httpx2 = mkPinnedPythonPackage {
    pname = "httpx2";
    version = "2.9.1";
    hash = "sha256-GTKnaHN+NmYpFYKDPadIzE5WPDN8+WcG/MwE+m5Ydko=";
    dependencies = with python3Packages; [
      anyio
      httpcore2
      idna
      truststore
    ];
    build-system = with python3Packages; [
      hatch-fancy-pypi-readme
      hatchling
      uv-dynamic-versioning
    ];
    pythonRelaxDeps = [ "idna" ];
  };

  mcp-types = mkPinnedPythonPackage {
    pname = "mcp_types";
    version = "2.0.0";
    hash = "sha256-19k5uShcmWGuiGa6de+F2jTRK6/idu+/TrahMXhtg3k=";
    dependencies = with python3Packages; [
      pydantic
      typing-extensions
    ];
    build-system = with python3Packages; [
      hatchling
      uv-dynamic-versioning
    ];
  };

  mcp-sdk = mkPinnedPythonPackage {
    pname = "mcp";
    version = "2.0.0";
    hash = "sha256-D0QOc1wT7Oi7GbxizwuG9DE0SEMvu3fTXhQDT04FByg=";
    dependencies = with python3Packages; [
      anyio
      cryptography
      httpx2
      jsonschema
      mcp-types
      opentelemetry-api
      pydantic
      pyjwt
      python-multipart
      sse-starlette
      starlette
      typing-extensions
      typing-inspection
      uvicorn
    ];
    build-system = with python3Packages; [
      hatchling
      uv-dynamic-versioning
    ];
  };
in
python3Packages.buildPythonApplication {
  pname = "sinnix-agent-gateway";
  version = "0.2.0";
  pyproject = true;
  src = ./.;

  build-system = [ python3Packages.setuptools ];

  dependencies = [ mcp-sdk ];

  nativeCheckInputs = [
    git
    python3Packages.pytest
    ripgrep
  ];

  makeWrapperArgs = [
    "--prefix"
    "PATH"
    ":"
    (lib.makeBinPath [
      git
      ripgrep
      fd
      gnused
      gnutar
      gzip
      coreutils
    ])
  ];

  checkPhase = ''
    runHook preCheck
    export SINNIX_GATEWAY_TEST_EXECUTABLE="$out/bin/sinnix-agent-gateway"
    # Bare `pytest` (default discovery), not a hardcoded file list, so a new
    # test file runs without needing a pkg.nix edit.
    pytest
    runHook postCheck
  '';

  pythonImportsCheck = [
    "sinnix_agent_gateway"
    "sinnix_agent_gateway.cli"
    "sinnix_agent_gateway.app"
    "sinnix_agent_gateway.audit"
    "sinnix_agent_gateway.beads"
    "sinnix_agent_gateway.jobs"
    "sinnix_agent_gateway.projects"
  ];

  meta = {
    description = "Trusted local MCP gateway for repo, command, artifact, and Sinnix operations";
    mainProgram = "sinnix-agent-gateway";
    license = lib.licenses.mit;
  };
}
