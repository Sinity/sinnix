{ lib, paths }:
let
  borgGlobToRegex =
    pattern:
    let
      globStarPlaceholder = "__SINNIX_BORG_GLOBSTAR__";
      withGlobStarPlaceholder = lib.replaceStrings [ "**" ] [ globStarPlaceholder ] pattern;
      escaped =
        lib.replaceStrings
          [
            "\\"
            "."
            "+"
            "("
            ")"
            "["
            "]"
            "{"
            "}"
            "^"
            "$"
            "|"
          ]
          [
            "\\\\"
            "\\."
            "\\+"
            "\\("
            "\\)"
            "\\["
            "\\]"
            "\\{"
            "\\}"
            "\\^"
            "\\$"
            "\\|"
          ]
          withGlobStarPlaceholder;
      withSingleStar = lib.replaceStrings [ "*" ] [ "[^/]*" ] escaped;
      withQuestion = lib.replaceStrings [ "?" ] [ "[^/]" ] withSingleStar;
    in
    "^${lib.replaceStrings [ globStarPlaceholder ] [ ".*" ] withQuestion}$";
  pathAndAncestors =
    path:
    let
      parts = lib.splitString "/" path;
    in
    lib.genList (index: lib.concatStringsSep "/" (lib.take (index + 1) parts)) (builtins.length parts);
in
exclude:
lib.any (
  path:
  lib.any (candidate: builtins.match (borgGlobToRegex exclude) candidate != null) (
    pathAndAncestors path
  )
) paths
