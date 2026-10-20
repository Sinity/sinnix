# Cleanup uses disposable repositories and a bounded process fixture, never the
# operator's project or worktree directories.
{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
    in
    {
      checks.worktree-reap =
        pkgs.runCommand "sinnix-worktree-reap-check"
          {
            nativeBuildInputs = [
              pkgs.python3
              pkgs.git
              pkgs.worktrunk
            ];
          }
          ''
            export WORKTREE_REAP_SOURCE=${../../scripts/sinnix-worktree-reap}
            python3 ${../../scripts/tests/test_worktree_reap.py}
            touch "$out"
          '';
    };
}
