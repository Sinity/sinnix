# Services auto-discovery
#
# All .nix files in this directory are automatically imported.
# Just add a new service file - no need to update this file.
{ lib, ... }:
{
  imports = lib.sinnix.mkAutoImports ./. [ ];
}
