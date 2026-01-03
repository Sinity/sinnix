{ inputs }: final: prev:
{
  lowdown = prev.lowdown.overrideAttrs (old: {
    # Ensure postInstall exists so nix's dependencies.nix can reference it
    postInstall = (old.postInstall or "") + ''
      # Placeholder to ensure attribute exists
    '';
  });
}
