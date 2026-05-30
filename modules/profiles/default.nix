# Profiles auto-discovery
#
# Host-level convenience aggregates that toggle several modules together
# (e.g. cloud/headless, workstation, edge-router). Profiles only set options;
# they never define new behavior.
{ lib, ... }:
{
  imports = lib.sinnix.mkAutoImports ./. [ ];
}
