# Local-AI inference engines built with CUDA.
#
# These are per-package overrides, NOT a global `nixpkgs.config.cudaSupport`
# flip — that would rebuild the world. CUDA itself ships as downloaded
# redistributables; only these named packages recompile. The
# `cuda-maintainers.cachix.org` substituter (see flake.nix nixConfig) usually
# turns even that recompile into a download.
#
# Host has exactly one GPU (RTX 3080, compute capability 8.6). Building from
# `aiPkgs.pkgsForCudaArch.sm_86` (nixpkgs' documented per-architecture package
# set: pkgs/development/cuda-modules, config.cudaCapabilities = ["8.6"]) means
# each ggml/CUDA derivation generates device code for that one architecture
# instead of the ~9 architectures nixpkgs targets by default
# (sm_75..sm_121a) — the difference between a multi-minute and a multi-hour
# rebuild on this host. Do not use plain `<pkgs>.<pkg>.override` for these
# without going through pkgsForCudaArch first.
#
# `aiPkgs` is instantiated from the separate `nixpkgs-ai` flake input (see
# flake.nix), not from `prev`/the shared system `pkgs`. Routine `nix flake
# update` bumps the shared `nixpkgs` constantly; if these packages were built
# from it, every bump would invalidate these derivation hashes and force a
# from-source CUDA recompile with no possible cache hit. nixpkgs-ai is bumped
# only deliberately (`sinnix update nixpkgs-ai`).
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
  # koboldcpp gates CUDA on `cublasSupport`, not `cudaSupport`.
  koboldcpp-cuda = aiPkgs.pkgsForCudaArch.sm_86.koboldcpp.override { cublasSupport = true; };
  llama-cpp-cuda = aiPkgs.pkgsForCudaArch.sm_86.llama-cpp.override { cudaSupport = true; };
  whisper-cpp-cuda = aiPkgs.pkgsForCudaArch.sm_86.whisper-cpp.override { cudaSupport = true; };
  # Prebuilt top-level attribute upstream; narrow it the same way so
  # services/ollama.nix's `pkgs.ollama-cuda` references pick this up for free.
  ollama-cuda = aiPkgs.pkgsForCudaArch.sm_86.ollama-cuda;
}
