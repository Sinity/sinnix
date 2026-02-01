# ========================================
# PACKAGES: Custom packages for sinnix
# ========================================
#
# Script packages are defined in scripts.nix registry.
# This file re-exports them and can add non-script packages.
{ inputs, ... }:
{
  perSystem =
    { pkgs, ... }:
    let
      scriptRegistry = import ./scripts.nix { inherit inputs pkgs; };
    in
    {
      # Export all script packages from registry
      packages = scriptRegistry.packages;
    };
}
