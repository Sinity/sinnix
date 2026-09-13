# One evaluation of command-registry.nix per perSystem `pkgs` instantiation.
#
# Apps and the development shell both render the same command, activation, and
# documentation data.  Publish it once through flake-parts rather than making
# each consumer apply the registry function independently.
{ inputs, ... }:
{
  perSystem =
    {
      pkgs,
      system,
      sinnixScriptRegistry,
      ...
    }:
    {
      _module.args.sinnixCommandRegistry = import ./command-registry.nix {
        inherit
          inputs
          pkgs
          system
          sinnixScriptRegistry
          ;
      };
    };
}
