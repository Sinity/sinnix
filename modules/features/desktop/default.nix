# Desktop features auto-discovery
#
# All .nix files and subdirs with default.nix are automatically imported.
# Just add a new feature file - no need to update this file.
{ lib, ... }:
{
  imports = lib.sinnix.mkAutoImports ./. [ ];
}
