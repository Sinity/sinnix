# One evaluation of scripts.nix's registry per perSystem `pkgs` instantiation.
#
# flake-parts shares `_module.args` across every perSystem-consuming module
# for one system the same way NixOS shares specialArgs across modules, so
# publishing the registry here once and having command-registry.nix (via
# dev-shell.nix) and packages.nix both destructure `sinnixScriptRegistry`
# replaces what used to be two separate `import ./scripts.nix { ... }`
# applications of the same 95-script frontmatter walk against the identical
# `pkgs`.
{ inputs, ... }:
{
  perSystem =
    { pkgs, ... }:
    {
      _module.args.sinnixScriptRegistry = import ./scripts.nix { inherit inputs pkgs; };
    };
}
