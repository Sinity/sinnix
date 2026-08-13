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
        "beads"
        "ccusage"
        "chatgpt-share-export"
        "lynchpin-cli"
        "lynchpin-python"
        "mcp-chrome-devtools"
        "mcp-firecrawl"
        "polylogue-cli"
        "polylogue-python"
        "polylogued"
        "sinnix"
        "sinnix-agent-control-mcp"
        "sinnix-agent-environment-doc"
        "sinnix-agent-gateway"
        "sinnix-capability-manifest"
        "sinnix-deslop"
        "sinnix-observe"
        "sinnix-phone-app"
        "sinnix-phone-app-install"
        "tunnel-client"
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
