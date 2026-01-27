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
  # Temporarily disabled patch due to nix-ai-tools update
  # TODO: Update prompt-subcommand.patch for new codex version
  codex = upstream.overrideAttrs (old: {
    patches = (old.patches or [ ]); # Removed custom patch
    patchFlags = (old.patchFlags or [ "-p1" ]);
    passthru = (old.passthru or { }) // {
      inherit upstream;
    };
  });
}
