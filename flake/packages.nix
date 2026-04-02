# ========================================
# PACKAGES: Custom packages for sinnix
# ========================================
#
# Script packages are defined in scripts.nix registry.
# This file re-exports them and can add non-script packages.
{ inputs, ... }:
{
  perSystem =
    { pkgs, lib, ... }:
    let
      scriptRegistry = import ./scripts.nix { inherit inputs pkgs; };
      publicPackageNames = [
        "ccusage"
        "lynchpin-python"
        "mcp-context7"
        "mcp-firecrawl"
        "normalize-agent-projects"
        "polylogue-cli"
        "polylogue-python"
        "render-agents"
        "sinnix-sentinel"
        "verify-agent-topology"
      ];
    in
    {
      # Keep the public flake package surface small. The full script registry is
      # still imported directly by modules/tests; only the explicitly supported
      # external package names stay under `packages` so `nix flake check` does
      # not walk every local convenience wrapper.
      packages = lib.getAttrs publicPackageNames scriptRegistry.packageSet;
    };
}
