# Modules auto-discovery
#
# All .nix files (except default.nix) and subdirs with default.nix
# are automatically imported. The lib/ directory is excluded because it
# contains helper functions, not NixOS modules.
{ lib, ... }:
{
  imports = lib.sinnix.mkAutoImports ./. [ "lib" ];
}
