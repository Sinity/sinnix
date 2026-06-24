# Local-AI inference engines built with CUDA.
#
# These are per-package overrides, NOT a global `nixpkgs.config.cudaSupport`
# flip — that would rebuild the world. CUDA itself ships as downloaded
# redistributables; only these named packages recompile. The
# `cuda-maintainers.cachix.org` substituter (see flake.nix nixConfig) usually
# turns even that recompile into a download.
#
# `ollama-cuda` is already a prebuilt top-level attribute upstream, so it needs
# no override here — services/ollama.nix references `pkgs.ollama-cuda` directly.
{ ... }:
_final: prev: {
  # koboldcpp gates CUDA on `cublasSupport`, not `cudaSupport`.
  koboldcpp-cuda = prev.koboldcpp.override { cublasSupport = true; };
  llama-cpp-cuda = prev.llama-cpp.override { cudaSupport = true; };
  whisper-cpp-cuda = prev.whisper-cpp.override { cudaSupport = true; };
}
