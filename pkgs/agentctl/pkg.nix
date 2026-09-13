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
  ...
}:
let
  # AgentCTL removals must not sweep unrelated repository state.
  # Remove this patch when upstream provides --no-internal-sweep.
  scopedWorktrunk = worktrunk.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [ ./worktrunk-no-internal-sweep.patch ];
  });
in
python3Packages.buildPythonApplication {
  pname = "agentctl";
  version = "0.1.0";
  pyproject = true;
  src = ./.;

  build-system = [ python3Packages.setuptools ];
  makeWrapperArgs = [
    "--prefix PATH : ${
      lib.makeBinPath [
        bash
        git
        gh
        beads
        scopedWorktrunk
        pueue
        nix
        systemd
      ]
    }"
  ];
  postInstall = ''
    install -Dm755 ${./agentctl-agent} "$out/libexec/agentctl-agent"
    sed -i '1c #!${bash}/bin/bash' "$out/libexec/agentctl-agent"
    wrapProgram "$out/libexec/agentctl-agent" \
      --prefix PATH : ${lib.makeBinPath [ bash coreutils python3Packages.python ]}
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

  pythonImportsCheck = [ "agentctl" ];

  meta = {
    description = "agentctl: jobs over pueue, lanes over worktrunk, gh and bd";
    mainProgram = "agentctl";
  };
}
