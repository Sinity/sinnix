{ inputs }:
final: _prev:
let
  inherit (final.stdenv.hostPlatform) system;
  upstream = inputs.nix-ai-tools.packages.${system}.codex;

  codexPatches = builtins.path {
    path = ../patch/codex;
    name = "sinnix-codex-patches";
  };
  codexPatch = name: codexPatches + "/${name}";
in
{
  codex = upstream.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [
      (codexPatch "prompt-subcommand.patch")
    ];
    passthru = (old.passthru or { }) // {
      inherit upstream;
    };
  });
}
