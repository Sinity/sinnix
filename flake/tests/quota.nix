# Provider quota normalization, redaction, and disagreement fixture.
{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      scriptRegistry = import ../scripts.nix { inherit inputs pkgs; };
    in
    {
      checks = {
        quota = scriptRegistry.packageSet.sinnix-quota;
        codexbar = scriptRegistry.packageSet.sinnix-quota.passthru.codexbar;
      };
    };
}
