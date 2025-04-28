# This file now expects `pkgs` and `craneLib` to be passed in.
# Example usage within a flake:
#
# packages.screen-pipe = pkgs.callPackage ./default.nix {
#   craneLib = inputs.crane.lib.${pkgs.system};
# };
#
{
  pkgs ? import <nixpkgs> {},
  craneLib, # Made craneLib a required argument
}:
let
  # craneLib must be passed in by the caller (e.g., flake.nix)
  src = craneLib.cleanCargoSource (craneLib.path ./.);

  # Common arguments for crane's build steps
  commonArgs = {
    inherit src;

    # System dependencies needed by Rust crates
    buildInputs = (with pkgs; [
    alsa-lib # for cpal/alsa
    bzip2 # for bzip2-sys
    dbus
    ffmpeg
    lzma # for lzma-sys
    oniguruma
    openssl
    sqlite
    xz # for ffmpeg-sidecar, lzma-sys
    zlib # for flate2
    zstd # for zstd-sys
  ]) ++ pkgs.lib.optionals pkgs.stdenv.isDarwin (with pkgs.darwin.apple_sdk.frameworks; [
    # macOS specific frameworks
    AppKit
    AVFoundation
    Carbon
    CoreAudio
    CoreFoundation
    CoreGraphics
    CoreMedia
    CoreServices
    CoreVideo
    Foundation # Implicitly needed by many ObjC crates
    IOKit
    Metal
    QuartzCore
    Security
      SystemConfiguration
    ]);

    nativeBuildInputs = with pkgs; [
      cmake # needed by various -sys crates (whisper, knf, ort, samplerate, zstd, bzip2, lzma, etc.)
      pkg-config
      # Note: crane handles bindgen setup automatically if clang is present
      pkgs.llvmPackages.libclang
      pkgs.clang # Needed by bindgen
    ];

    # Environment variables needed for building some crates
    LIBCLANG_PATH = "${pkgs.llvmPackages.libclang.lib}/lib";
    # Add other environment variables if needed during the build process
    # e.g. OPENSSL_DIR = "${pkgs.openssl.dev}"; # Crane might handle some common ones
  };

  # Use crane to fetch dependencies and build the crate
  cargoArtifacts = craneLib.buildDepsOnly commonArgs;

  screen-pipe = craneLib.buildPackage (commonArgs // {
    inherit cargoArtifacts;
    pname = "screen-pipe"; # Explicitly set pname here
    version = "0.2.74"; # Explicitly set version here
    doCheck = false; # Disable tests for now
  });

in
  screen-pipe
