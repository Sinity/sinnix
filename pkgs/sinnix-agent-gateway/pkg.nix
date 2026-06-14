{
  python3Packages,
  lib,
  git,
  ripgrep,
  fd,
  gnused,
  gnutar,
  gzip,
  coreutils,
  ...
}:
python3Packages.buildPythonApplication {
  pname = "sinnix-agent-gateway";
  version = "0.1.0";
  pyproject = true;
  src = ./.;

  build-system = [ python3Packages.setuptools ];

  # Runtime is stdlib-only. External binaries are placed on PATH for the tools
  # that shell out to git/rg/fd/tar; host profiles can still add cargo/nix/etc.
  dependencies = [ ];

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

  pythonImportsCheck = [
    "sinnix_agent_gateway"
    "sinnix_agent_gateway.cli"
    "sinnix_agent_gateway.server"
  ];

  meta = {
    description = "Trusted local MCP gateway for repo, command, artifact, and Sinnix operations";
    mainProgram = "sinnix-agent-gateway";
    license = lib.licenses.mit;
  };
}
