{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
    in
    {
      checks.batch-worker-toolbelt =
        pkgs.runCommand "batch-worker-toolbelt-check"
          {
            # `batch-worker done` validates through `agentctl result validate-worker`.
            nativeBuildInputs = [
              inputs.self.packages.${system}.agentctl
              pkgs.bash
              pkgs.coreutils
              pkgs.git
              pkgs.gnugrep
              pkgs.python3
            ];
          }
          ''
            worker="$TMPDIR/batch-worker"
            cp ${../../dots/_ai/skills/agent-runtime/scripts/batch-worker} "$worker"
            patchShebangs "$worker"
            chmod +x "$worker"
                ${pkgs.bash}/bin/bash ${./batch-worker-toolbelt.sh} "$worker" ${../../dots/claude/agents/schemas/worker.schema.json}
                touch "$out"
          '';
    };
}
