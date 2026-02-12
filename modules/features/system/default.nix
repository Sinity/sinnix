# System features auto-discovery
{ lib, ... }:
{
  imports = lib.sinnix.mkAutoImports ./. [ ];
}
