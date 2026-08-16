/*
  `sinnix` — generated meta-CLI front door over the packaged script registry.

  Consumes the `registry` produced by `script-discovery.nix` (name ->
  { description; runtimeInputs; tier; package; }) and renders a single
  dispatcher shell script at eval time:

    sinnix help              lists every packaged script, `name — description`,
                              grouped by tier when more than one tier is in use
    sinnix <name> [args...]  execs the matching script package's binary

  Name resolution prefers an exact registry match (covers scripts that are
  not `sinnix-`-prefixed, e.g. `oracle`, `rawlog`), then
  falls back to a `sinnix-<name>` prefix lookup (`sinnix rerank` ->
  `sinnix-rerank`). Unknown names get a substring-based "did you mean"
  suggestion list rather than a bare failure.

  The full data table (registered name / short display name / store binary
  path / description) is baked into the script as a static TSV heredoc, so
  the dispatcher does no filesystem discovery of its own at runtime and has
  no dependency on the invoking PATH beyond `awk`/`coreutils`.
*/
{
  lib,
  pkgs,
  registry,
}:
let
  inherit (lib)
    concatStringsSep
    filter
    foldl'
    genList
    hasPrefix
    length
    mapAttrsToList
    max
    removePrefix
    sort
    stringLength
    unique
    ;

  entries = mapAttrsToList (name: meta: {
    inherit name;
    description = meta.description;
    displayName = if hasPrefix "sinnix-" name then removePrefix "sinnix-" name else name;
    binPath = "${meta.package}/bin/${name}";
    tier = meta.tier;
  }) registry;

  byDisplayName = a: b: a.displayName < b.displayName;
  sorted = sort byDisplayName entries;

  count = length sorted;

  tiers = sort (a: b: a < b) (unique (map (e: e.tier) sorted));
  multiTier = length tiers > 1;

  maxWidth = foldl' (acc: e: max acc (stringLength e.displayName)) 0 sorted;

  padRight = width: str: str + concatStringsSep "" (genList (_: " ") (width - stringLength str));

  helpLineFor = e: "  ${padRight maxWidth e.displayName}  — ${e.description}";

  helpBody =
    if multiTier then
      concatStringsSep "\n\n" (
        map (t: "${t}:\n" + concatStringsSep "\n" (map helpLineFor (filter (e: e.tier == t) sorted))) tiers
      )
    else
      concatStringsSep "\n" (map helpLineFor sorted);

  # Static lookup table baked into the script: name <TAB> displayName <TAB>
  # binPath <TAB> description. Rendered inside a quoted heredoc (no shell
  # interpolation of its contents).
  tableText = concatStringsSep "\n" (
    map (e: "${e.name}\t${e.displayName}\t${e.binPath}\t${e.description}") sorted
  );

  scriptText = ''
    set -euo pipefail

    list_scripts() {
      cat <<'SINNIX_TABLE_EOF'
    ${tableText}
    SINNIX_TABLE_EOF
    }

    print_help() {
      cat <<'SINNIX_HELP_EOF'
    sinnix -- front door for ${toString count} Sinnix scripts

    Usage:
      sinnix <command> [args...]
      sinnix help

    Commands may be invoked by their short name (e.g. `sinnix rerank`) or
    their full script name (e.g. `sinnix sinnix-rerank`).

    Commands:
    ${helpBody}
    SINNIX_HELP_EOF
    }

    resolve() {
      local query="$1"
      local hit
      hit="$(list_scripts | awk -F'\t' -v q="$query" '$1==q{print;exit}')"
      if [ -z "$hit" ]; then
        hit="$(list_scripts | awk -F'\t' -v q="sinnix-$query" '$1==q{print;exit}')"
      fi
      printf '%s' "$hit"
    }

    suggest() {
      local query="$1"
      list_scripts | awk -F'\t' -v q="$query" '
        BEGIN { ql = tolower(q) }
        index(tolower($1), ql) > 0 || index(tolower($2), ql) > 0 { print "  " $2 " — " $4 }
      '
    }

    if [ "$#" -eq 0 ]; then
      print_help
      exit 0
    fi

    cmd="$1"
    shift

    case "$cmd" in
      help | -h | --help)
        print_help
        exit 0
        ;;
    esac

    hit="$(resolve "$cmd")"
    if [ -n "$hit" ]; then
      binpath="$(printf '%s' "$hit" | cut -f3)"
      exec "$binpath" "$@"
    fi

    echo "sinnix: unknown command '$cmd'" >&2
    matches="$(suggest "$cmd")"
    if [ -n "$matches" ]; then
      echo "Did you mean:" >&2
      echo "$matches" >&2
    else
      echo "Run 'sinnix help' to list all ${toString count} commands." >&2
    fi
    exit 1
  '';
in
pkgs.writeShellApplication {
  name = "sinnix";
  runtimeInputs = [
    pkgs.gawk
    pkgs.coreutils
  ];
  text = scriptText;
  meta.description = "Discoverable front door over the packaged Sinnix script registry";
}
