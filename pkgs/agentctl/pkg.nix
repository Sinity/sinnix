{
  lib,
  python3Packages,
  bash,
  coreutils,
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
  # AgentCTL removals must not sweep unrelated repository state.
  # Remove this patch when upstream provides --no-internal-sweep.
  scopedWorktrunk = worktrunk.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [ ./worktrunk-no-internal-sweep.patch ];
  });
  # Shared by the CLI wrapper and in-process consumers such as the gateway.
  # Importing this Python package does not execute its command-line wrapper.
  runtimeDependencies = [
    bash
    git
    gh
    beads
    scopedWorktrunk
    pueue
    nix
    systemd
  ];
in
python3Packages.buildPythonApplication {
  pname = "agentctl";
  version = "0.1.0";
  pyproject = true;
  src = ./.;

  build-system = [ python3Packages.setuptools ];
  dependencies = [ sinnix-lib ];
  makeWrapperArgs = [
    "--prefix PATH : ${lib.makeBinPath runtimeDependencies}"
  ];
  # The backend adapter has exactly one copy in the repository: the
  # agent-runtime skill script. agentctl's own default config points at that
  # path (`config.DEFAULT_SKILLS_DIR`), so a second tracked copy here could
  # only ever drift out of the route that actually runs.
  postInstall = ''
    install -Dm755 ${../../dots/_ai/skills/agent-runtime/scripts/run_agent_prompt.sh} "$out/libexec/agentctl-agent"
    sed -i '1c #!${bash}/bin/bash' "$out/libexec/agentctl-agent"
    wrapProgram "$out/libexec/agentctl-agent" \
      --prefix PATH : ${
        lib.makeBinPath [
          bash
          coreutils
          python3Packages.python
        ]
      }
    ln -s ../libexec/agentctl-agent "$out/bin/agentctl-agent"
  '';
  nativeCheckInputs = [
    python3Packages.pytest
    git
    beads
    scopedWorktrunk
    pueue
  ];

  checkPhase = ''
    runHook preCheck
    pytest
    runHook postCheck
  '';

  passthru = { inherit runtimeDependencies; };

  pythonImportsCheck = [ "agentctl" ];

  meta = {
    description = "agentctl: jobs over pueue, lanes over worktrunk, gh and bd";
    mainProgram = "agentctl";
  };
}
