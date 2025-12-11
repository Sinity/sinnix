{ inputs }:
final: _prev:
let
  inherit (final.stdenv.hostPlatform) system;
  upstream = inputs.polylogue.packages.${system}.polylogue;
in
{
  polylogue = upstream.overrideAttrs (old: {
    doCheck = false;
    doInstallCheck = false;
    pythonImportsCheck = [ ];
    passthru = (old.passthru or { }) // {
      inherit upstream;
    };
  });
}
