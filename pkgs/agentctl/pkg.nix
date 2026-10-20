{
  lib,
  python3Packages,
  bash,
  coreutils,
  findutils,
  git,
  gh,
  beads,
  worktrunk,
  pueue,
  nix,
  systemd,
  sinnix-lib,
  ...
}:
let
  # Shared by the CLI wrapper and in-process consumers such as the gateway.
  # Importing this Python package does not execute its command-line wrapper.
  runtimeDependencies = [
    bash
    coreutils
    findutils
    git
    gh
    beads
    worktrunk
    pueue
    nix
    systemd
  ];
in
python3Packages.buildPythonApplication {
  pname = "agentctl";
  version = "0.1.0";
  pyproject = true;
  src = lib.fileset.toSource {
    root = ./.;
    fileset = lib.fileset.unions [
      ./pyproject.toml
      ./agentctl
    ];
  };
  doCheck = false;

  build-system = [ python3Packages.setuptools ];
  dependencies = [
    sinnix-lib
  ];
  makeWrapperArgs = [
    "--prefix PATH : ${lib.makeBinPath runtimeDependencies}"
  ];
  passthru = { inherit runtimeDependencies; };

  pythonImportsCheck = [ "agentctl" ];

  meta = {
    description = "agentctl: native project jobs and retained history";
    mainProgram = "agentctl";
  };
}
