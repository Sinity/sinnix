{
  lib,
  python3Packages,
  bash,
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
