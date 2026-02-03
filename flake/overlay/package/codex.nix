{ inputs, ... }:
final: _prev:
let
  inherit (final.stdenv.hostPlatform) system;
  upstream = inputs.nix-ai-tools.packages.${system}.codex;
in
{
  codex = upstream.overrideAttrs (old: {
    patches = (old.patches or [ ]);
    patchFlags = (old.patchFlags or [ "-p1" ]);
    passthru = (old.passthru or { }) // {
      inherit upstream;
    };
  });
}
