_:
# nvibrant 1.2.0-unstable: the open-gpu-kernel-modules FOD uses fetchTags=true,
# so its hash breaks whenever NVIDIA adds new driver tags to the upstream repo.
# Patch via overrideDerivation to correct the outputHash of the open-gpu source.
# Update this hash (and latestDriverVersion in nixpkgs nvibrant) when nixpkgs
# next bumps nvibrant.
#
# recheck: every nixpkgs bump that touches nvibrant (fetchTags growth alone
# can break this even without a version bump) — this hash and nixpkgs'
# latestDriverVersion must be updated together or the build fails outright
# (loud failure, not silent staleness, but still worth a standing marker).
_: prev: {
  nvibrant =
    let
      fixedOpenGpu = prev.nvibrant.passthru.srcAttrs.open-gpu.overrideDerivation (_: {
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
