# Docling — PDF/office document conversion to structured markdown, for the
# data lake. Packaged straight from nixpkgs rather than a uv-tool bootstrap,
# so Nix owns the whole closure instead of a first-run install into
# ~/.local/share/uv.
{
  mkFeatureModule,
  pkgs,
  ...
}@args:
mkFeatureModule {
  path = [
    "cli"
    "docling"
  ];
  description = "Docling PDF/office document conversion to markdown";
  configFn =
    { pkgs, ... }:
    {
      environment.systemPackages = [ pkgs.docling ];
    };
} args
