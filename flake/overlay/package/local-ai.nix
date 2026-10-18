# CUDA builds: local-AI inference engines and the Sunshine game streamer.
#
# These come from a CUDA-enabled instance of the separate `nixpkgs-ai` input,
# not a global `nixpkgs.config.cudaSupport` flip, which would rebuild the
# world. They are used exactly as nixpkgs defines them: cache.nixos-cuda.org
# (see flake.nix nixConfig) builds the default CUDA configuration of
# nixos-unstable, so any override, patch, source bump or narrowed
# architecture set (`pkgsForCudaArch`) turns a download into an hours-long
# local CUDA compile.
#
# nixpkgs-ai is pinned separately from the shared `nixpkgs` so routine
# `nix flake update` does not move these derivations; bump it deliberately
# (`sinnix update nixpkgs-ai`) to a revision the CUDA cache has built.
{ inputs, ... }:
final: _prev:
let
  inherit (final.stdenv.hostPlatform) system;
  aiPkgs = import inputs.nixpkgs-ai {
    inherit system;
    config = {
      allowUnfree = true;
      cudaSupport = true;
    };
    overlays = [ ];
  };
in
{
  llama-cpp-cuda = aiPkgs.llama-cpp;
  sunshine-cuda = aiPkgs.sunshine;
  inherit (aiPkgs) ollama-cuda;
}
