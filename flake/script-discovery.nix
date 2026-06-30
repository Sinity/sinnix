/*
  Script discovery for sinnix.

  Walks `scripts/` and builds a package registry from per-file frontmatter.
  A script opts into packaging by including a frontmatter block:

      # @sinnix-package
      # description: One-line description (required)
      # runtimeInputs: bash coreutils jq        (space-separated, may be empty)
      # tier: default                           (optional; default | heavy | dev)

  The script is copied into the Nix store with its shebang patched, so Python /
  bash / zsh dispatch is automatic inside sandboxed builds. `runtimeInputs`
  packages land on PATH for both wrapper and script.

  A script that should NOT be packaged (e.g. launched directly by Hyprland)
  declares:

      # @sinnix-package: skip

  Every file under `scripts/` MUST have one of the two markers; otherwise
  evaluation fails. This makes silent staleness impossible.

  Package names default to the file basename. Dotted runtime-input names
  (e.g. `python3Packages.speedtest-cli`, `linuxPackages.turbostat`) are
  resolved via attribute path. A prefix `@` references another packaged
  script in the registry (cyclic resolution is fine — Nix is lazy).
*/
{ lib, pkgs }:
let
  inherit (lib)
    attrByPath
    filter
    hasPrefix
    listToAttrs
    nameValuePair
    removeSuffix
    splitString
    trim
    ;

  # ------------------------------------------------------------------
  # Frontmatter parser
  # ------------------------------------------------------------------

  stripCommentPrefix =
    line:
    let
      t = trim line;
    in
    if hasPrefix "# " t then
      removeSuffix "\r" (lib.substring 2 (lib.stringLength t) t)
    else if hasPrefix "#" t then
      removeSuffix "\r" (lib.substring 1 (lib.stringLength t) t)
    else
      null;

  # Find the @sinnix-package block in the first ~40 lines. Returns:
  #   { mode = "skip"; }
  #   { mode = "package"; fields = { description = ...; runtimeInputs = ...; ... }; }
  #   { mode = "missing"; }
  parseFrontmatter =
    text:
    let
      lines = lib.take 60 (splitString "\n" text);
      stripped = map stripCommentPrefix lines;
      indexed = lib.imap0 (i: v: {
        inherit i;
        line = v;
      }) stripped;
      markerLines = filter (e: e.line != null && (lib.hasPrefix "@sinnix-package" (trim e.line))) indexed;
    in
    if markerLines == [ ] then
      { mode = "missing"; }
    else
      let
        marker = lib.head markerLines;
        markerText = trim marker.line;
      in
      if markerText == "@sinnix-package: skip" || markerText == "@sinnix-package:skip" then
        { mode = "skip"; }
      else
        let
          # Walk forward from the marker. Stop at the first non-comment line
          # or comment line that does not look like `key: value`.
          tail = lib.drop (marker.i + 1) stripped;
          collect =
            acc: ls:
            if ls == [ ] then
              acc
            else
              let
                head = lib.head ls;
                rest = lib.tail ls;
              in
              if head == null then
                acc
              else
                let
                  trimmed = trim head;
                  colonIdx = lib.findFirst (i: lib.substring i 1 trimmed == ":") (-1) (
                    lib.range 0 (lib.stringLength trimmed - 1)
                  );
                in
                if colonIdx < 0 then
                  acc
                else
                  let
                    key = trim (lib.substring 0 colonIdx trimmed);
                    val = trim (lib.substring (colonIdx + 1) (lib.stringLength trimmed) trimmed);
                  in
                  collect (acc // { ${key} = val; }) rest;
        in
        {
          mode = "package";
          fields = collect { } tail;
        };

  # ------------------------------------------------------------------
  # Package builder
  # ------------------------------------------------------------------

  splitWords =
    s:
    let
      raw = splitString " " s;
    in
    filter (w: w != "") (map trim raw);

  resolvePkg =
    scriptPackages: token:
    if token == "" then
      null
    else if hasPrefix "@" token then
      let
        name = lib.substring 1 (lib.stringLength token) token;
      in
      scriptPackages.${name}.package or (throw "script-discovery: unknown sibling script @${name}")
    else
      let
        path = splitString "." token;
      in
      attrByPath path (throw "script-discovery: pkgs.${token} does not exist") pkgs;

  mkScriptPackage =
    scriptPackages: name: filePath: fields:
    let
      description = fields.description or (throw "script ${name}: frontmatter missing `description`");
      runtimeInputsRaw = splitWords (fields.runtimeInputs or "");
      runtimeInputs = filter (p: p != null) (map (resolvePkg scriptPackages) runtimeInputsRaw);
      tier = fields.tier or "default";
      patchedScript =
        pkgs.runCommand "${name}-script"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.python3
              pkgs.zsh
            ];
          }
          ''
            install -Dm755 ${filePath} "$out"
            patchShebangs "$out"
          '';
      pkg = pkgs.writeShellApplication {
        inherit name runtimeInputs;
        text = ''
          exec ${patchedScript} "$@"
        '';
      };
    in
    {
      inherit description runtimeInputs tier;
      package = pkg;
    };

  # ------------------------------------------------------------------
  # Discovery
  # ------------------------------------------------------------------

  discover =
    scriptsDir:
    let
      entries = builtins.readDir scriptsDir;
      fileNames = lib.attrNames (lib.filterAttrs (_: kind: kind == "regular") entries);
      classified = map (
        fname:
        let
          path = scriptsDir + "/${fname}";
          parsed = parseFrontmatter (builtins.readFile path);
        in
        {
          inherit fname path;
          frontmatter = parsed;
        }
      ) fileNames;
      missing = filter (e: e.frontmatter.mode == "missing") classified;
      packaged = filter (e: e.frontmatter.mode == "package") classified;
      skipped = filter (e: e.frontmatter.mode == "skip") classified;
    in
    if missing != [ ] then
      throw ''
        script-discovery: the following files in scripts/ have no @sinnix-package frontmatter:
          ${lib.concatStringsSep "\n          " (map (e: e.fname) missing)}
        Add either:
            # @sinnix-package
            # description: ...
            # runtimeInputs: ...
        or, if the script is launched directly (e.g. by hyprland) and does not
        need PATH/runtimeInputs packaging:
            # @sinnix-package: skip
      ''
    else
      {
        inherit packaged skipped;
        registry =
          let
            scriptPackages = listToAttrs (
              map (
                e:
                let
                  name = e.frontmatter.fields.name or e.fname;
                in
                nameValuePair name (mkScriptPackage scriptPackages name e.path e.frontmatter.fields)
              ) packaged
            );
          in
          scriptPackages;
      };
in
{
  inherit discover parseFrontmatter;
}
