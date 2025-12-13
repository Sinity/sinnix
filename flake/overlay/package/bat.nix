{ ... }:
final: prev:
let
  updatedJsonSyntax = final.fetchurl {
    url = "https://raw.githubusercontent.com/sublimehq/Packages/0d07278457f43f56c0f2c95f883621ea6ed2d370/JSON/JSON.sublime-syntax";
    sha256 = "sha256-fit/TAmpFwyVi3oVvNq7f9Oia5BQ6qMU2tHlppyN9SQ=";
  };
in
{
  bat = prev.bat.overrideAttrs (old: {
    # bat 0.26.0 bundles a Dockerfile syntax referencing the newer JSON
    # grammar's `arrays` context (see sharkdp/bat#3446) while still
    # shipping the older JSON definition. Replace it here so cache builds
    # succeed without warnings until upstream releases a fix.
    postPatch = (old.postPatch or "") + ''
      mkdir -p assets/syntaxes/01_Packages/JSON
      cp ${updatedJsonSyntax} assets/syntaxes/01_Packages/JSON/JSON.sublime-syntax
    '';
  });
}
