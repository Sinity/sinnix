# Read-only operations reducer protocol and source-health fixture.
{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      scriptRegistry = import ../scripts.nix { inherit inputs pkgs; };
    in
    {
      checks.ops-reducer = scriptRegistry.packageSet.sinnix-ops-reducer;
    };
}
