# Bundles auto-discovery
#
# Bundles are convenience presets that enable groups of features.
# All .nix files are automatically imported.
{ lib, ... }:
{
  imports = lib.sinnix.mkAutoImports ./. [ ];
}
