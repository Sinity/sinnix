# Features auto-discovery
#
# All subdirs with default.nix are automatically imported.
# Each domain (cli, desktop, dev) handles its own module discovery.
{ lib, ... }:
{
  imports = lib.sinnix.mkAutoImports ./. [];
}
