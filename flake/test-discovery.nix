/*
  Test spec discovery.

  Walks the configured roots for `*.test.nix` files. Each file is a
  function that takes the helper bag (`lib`, `expect`, `mkFeatureTest`,
  `mkServiceTest`, `hmFor`, `inputs`) and returns either
  a single test spec (the result of `mkFeatureTest`/etc.) or a list of
  specs.

  Co-locating tests with the modules they exercise replaces the previous
  3199-LOC `flake/tests.nix` monolith. Adding a new module test is now a
  single new file with no central registration.
*/
{ lib }:
let
  inherit (lib)
    concatLists
    concatMap
    hasSuffix
    isList
    mapAttrsToList
    ;

  collectFiles =
    pred: dir:
    let
      entries = builtins.readDir dir;
    in
    concatLists (
      mapAttrsToList (
        name: kind:
        let
          path = dir + "/${name}";
        in
        if kind == "directory" then
          collectFiles pred path
        else if kind == "regular" && pred name then
          [ path ]
        else
          [ ]
      ) entries
    );

  discoverTestSpecs =
    {
      roots,
      helpers,
    }:
    let
      isTestFile = name: hasSuffix ".test.nix" name;
      paths = concatMap (root: collectFiles isTestFile root) roots;
      results = concatMap (
        path:
        let
          r = import path helpers;
        in
        if isList r then r else [ r ]
      ) paths;
    in
    results;
in
{
  inherit discoverTestSpecs collectFiles;
}
