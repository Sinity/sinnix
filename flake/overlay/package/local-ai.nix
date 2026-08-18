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
# flake.nix), not from `prev`/the shared system `pkgs`: routine `nix flake
# update` bumps the shared `nixpkgs` constantly, and any bump would
# invalidate these derivation hashes and force a from-source CUDA recompile
# with no possible cache hit. nixpkgs-ai is bumped only deliberately
# (`sinnix update nixpkgs-ai`).
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
  # recheck: whenever nixpkgs-ai is deliberately bumped (`sinnix update
  # nixpkgs-ai`) — koboldcpp may rename/unify this option flag to match
  # llama-cpp's `cudaSupport`, which would silently no-op this
  # override if the old attr name is simply ignored rather than erroring.
  #
  # sinnix-dvwm: upstream's package.nix postPatch strips `-lcuda` out of the
  # Makefile's CUBLASLD_FLAGS so the build never needs a link-time
  # libcuda.so (nixpkgs doesn't ship the real driver lib; only
  # addDriverRunpath's runtime search does). But koboldcpp's ggml still
  # calls real CUDA *driver*-API functions unconditionally — cuMemCreate,
  # cuMemMap, cuGetErrorString, etc., only exported by libcuda.so.1 — from
  # its VMM pooled allocator. The newest vendored ggml fork
  # (ggml-cuda.cu) can disable that path at compile time via
  # -DGGML_CUDA_NO_VMM, but koboldcpp additionally vendors two older ggml
  # forks for legacy model formats (otherarch/ggml_v3-cuda.cu compiles the
  # same cuMemCreate/cuMemMap/cuGetErrorString calls with no such guard at
  # all — verified: -DGGML_CUDA_NO_VMM alone still leaves `U cuMemCreate`
  # in koboldcpp_cublas.so), so disabling VMM per-macro is a losing chase
  # across forks. Fix at the link layer upstream's postPatch broke instead:
  # keep `-lcuda`, add nixpkgs' CUDA driver *stub* lib (built for exactly
  # this — link-time only, real driver resolved at runtime) to
  # CUBLASLD_FLAGS's search path, and autoAddDriverRunpath fixes up the
  # built .so's RUNPATH to the real host driver so the stub is never
  # touched again once installed.
  koboldcpp-cuda =
    let
      cudaPkgs = aiPkgs.pkgsForCudaArch.sm_86;
    in
    (cudaPkgs.koboldcpp.override { cublasSupport = true; }).overrideAttrs (old: {
      postPatch = ''
        nixLog "patching $PWD/Makefile to keep -lcuda but resolve it against the CUDA driver stub lib (sinnix-dvwm)"
        substituteInPlace "$PWD/Makefile" \
          --replace-fail \
            'CUBLASLD_FLAGS = -lcuda -lcublas' \
            'CUBLASLD_FLAGS = -lcuda -L${cudaPkgs.cudaPackages.cuda_cudart}/lib/stubs -lcublas'
      '';
      nativeBuildInputs = old.nativeBuildInputs ++ [ cudaPkgs.autoAddDriverRunpath ];
    });
  # Muse Glimmer support landed after the nixpkgs-ai package snapshot. Keep
  # the existing CUDA package recipe and replace only its pinned upstream
  # source until nixpkgs-ai carries b10353 or newer.
  llama-cpp-cuda =
    (aiPkgs.pkgsForCudaArch.sm_86.llama-cpp.override { cudaSupport = true; }).overrideAttrs
      (_old: {
        # llama.cpp embeds this value as a C++ integer in build-info.cpp.
        version = "10353";
        src = final.fetchFromGitHub {
          owner = "ggml-org";
          repo = "llama.cpp";
          rev = "b10353";
          hash = "sha256-MQP91lL8zQLYcnYw5GlkMvH5sXiES+C6L4/1G3Y6TPY=";
        };
        npmDepsHash = "sha256-2Q7XhaLAArmviOLdQsNbYTfdyDE5pW9lR26cRHEVl9k=";
      });
  # Prebuilt top-level attribute upstream; narrow it the same way so
  # services/ollama.nix's `pkgs.ollama-cuda` references pick this up for free.
  ollama-cuda = aiPkgs.pkgsForCudaArch.sm_86.ollama-cuda;
}
