# Every script a GitHub workflow runs must be a file this repository ships.
# A workflow is evaluated only on the hosted runner, so a step that names a
# deleted path fails there and nowhere else; this check answers locally.
#
# The flake source is the git tree, so `builtins.pathExists` against it is
# "tracked file", not "present in someone's working copy".
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
  repoRoot = ../..;

  # Repository-relative script paths named anywhere in a workflow file.
  scriptPathsIn =
    directory:
    let
      workflows = builtins.filter (name: lib.hasSuffix ".yml" name || lib.hasSuffix ".yaml" name) (
        builtins.attrNames (builtins.readDir directory)
      );
      tokensOf =
        name:
        builtins.filter (
          piece: builtins.isString piece && builtins.match "[A-Za-z0-9_./-]+[.](py|sh)" piece != null
        ) (builtins.split "[^A-Za-z0-9_./-]+" (builtins.readFile (directory + "/${name}")));
    in
    lib.unique (lib.concatMap tokensOf workflows);

  missingIn =
    directory:
    builtins.filter (path: !builtins.pathExists (repoRoot + "/${path}")) (scriptPathsIn directory);

  unresolved = missingIn ../../.github/workflows;
  # The same scan over a fixture that names one deleted and one shipped
  # script: it pins what the scan detects, so an empty real result is a
  # measured absence rather than a scan that stopped looking.
  fixtureUnresolved = missingIn ./fixtures/workflow-paths;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
    in
    {
      checks.github-workflow-script-paths =
        pkgs.runCommand "github-workflow-script-paths"
          {
            unresolved = builtins.concatStringsSep " " unresolved;
            fixtureUnresolved = builtins.concatStringsSep " " fixtureUnresolved;
          }
          ''
            if [ -n "$unresolved" ]; then
              echo "workflow steps name scripts that this repository does not ship: $unresolved" >&2
              exit 1
            fi
            expected="scripts/a-script-this-repository-does-not-ship.py"
            if [ "$fixtureUnresolved" != "$expected" ]; then
              echo "the scan reported '$fixtureUnresolved' for the fixture, expected '$expected'" >&2
              exit 1
            fi
            touch "$out"
          '';
    };
}
