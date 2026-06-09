{ inputs, overlayLib, ... }:
# nvibrant 1.2.0-unstable: the open-gpu-kernel-modules FOD uses fetchTags=true,
# so its hash breaks whenever NVIDIA adds new driver tags to the upstream repo.
# Patch via overrideDerivation to correct the outputHash of the open-gpu source.
# Update this hash (and latestDriverVersion in nixpkgs nvibrant) when nixpkgs
# next bumps nvibrant.
final: prev: {
  nvibrant =
    let
      fixedOpenGpu = prev.nvibrant.passthru.srcAttrs.open-gpu.overrideDerivation (drv: {
        outputHash = "sha256-mSSKaIMJrlM2yiM7DO0cJhKGRYZJmZAKBpr9dVh55no=";
      });
    in
    prev.nvibrant.overrideAttrs (old: {
      passthru = old.passthru // {
        srcAttrs = old.passthru.srcAttrs // {
          open-gpu = fixedOpenGpu;
        };
      };

      srcs = builtins.attrValues (old.passthru.srcAttrs // { open-gpu = fixedOpenGpu; });
    });
}
