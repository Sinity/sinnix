{ lib }:
let
  normalizeRel = path:
    if lib.hasPrefix "/" path then
      lib.substring 1 (lib.stringLength path) path
    else
      path;
in
{
  mkAssetPath =
    flakeRoot: relPath:
    let
      root = builtins.toString flakeRoot;
    in
    root + "/nixos/assets/" + normalizeRel relPath;

  mkScriptPath =
    flakeRoot: relPath:
    let
      root = builtins.toString flakeRoot;
    in
    root + "/scripts/" + normalizeRel relPath;
}
