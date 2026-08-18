/*
  Script discovery for sinnix.

  Walks `scripts/` and builds a package registry from per-file frontmatter.
  A script opts into packaging by including a frontmatter block:

      # @sinnix-package
      # description: One-line description (required)
      # runtimeInputs: bash coreutils jq        (space-separated, may be empty)
      # pythonPackages: @sinnix-lib numpy       (optional; see below)
      #
      # Every packaged script already gets coreutils, gawk, gnugrep, gnused,
      # findutils, curl, jq and ffmpeg on PATH without asking. Declare only
      # the non-obvious things (pipewire, android-tools, conntrack-tools).
      # tier: default                           (optional; default | heavy | dev)

  The script is copied into the Nix store with its shebang patched, so Python /
  bash / zsh dispatch is automatic inside sandboxed builds. `runtimeInputs`
  packages land on PATH for both wrapper and script.

  `pythonPackages` is a different axis and the only way a Python script can
  import a library: PATH is irrelevant to `import`, because the kernel
  resolves the patched `#!/nix/store/.../python3` shebang directly and that
  interpreter's sys.path is fixed at build time. Naming packages here builds a
  `python3.withPackages` interpreter for THAT script and patches its shebang
  against it instead of the bare `pkgs.python3`. Tokens resolve in
  `pkgs.python3Packages` (dotted attribute paths allowed); a leading `@`
  references a sibling non-script package (e.g. `@sinnix-lib`). Scripts that
  do not name the field -- nearly all of them -- keep bare python3 and pay
  neither the extra eval nor the wrapper build.

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
{
  lib,
  pkgs,
  # Non-script packages (pkgs/ libraries registered in flake/scripts.nix)
  # that scripts may reference with the same `@name` syntax as siblings.
  siblingExtras ? { },
}:
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
      scriptPackages.${name}.package or siblingExtras.${name}
        or (throw "script-discovery: unknown sibling script @${name}")
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
      declaredInputs = filter (p: p != null) (map (resolvePkg scriptPackages) runtimeInputsRaw);
      # Every packaged script gets the ordinary shell toolkit whether or not
      # it names it. An omitted-but-used tool dies with exit 127 at runtime,
      # and shellcheck cannot see that class — it knows nothing about
      # frontmatter or the generated PATH. These cost nothing: they are
      # already in the system closure, so a wrapper PATH entry adds a
      # reference, not a download, and per-script declaration bought no
      # isolation on a single-user host. Frontmatter is still how a script
      # asks for something NON-obvious (pipewire, android-tools,
      # conntrack-tools), which is the part worth reviewing.
      baseRuntimeInputs = with pkgs; [
        coreutils
        gawk
        gnugrep
        gnused
        findutils
        curl
        jq
        ffmpeg
      ];
      runtimeInputs = lib.unique (baseRuntimeInputs ++ declaredInputs);
      tier = fields.tier or "default";
      # Optional `docs: docs/foo.md` frontmatter key, consumed by
      # modules/lib/capability-index.nix in place of (falling back to) its
      # docs/<name>.md filename convention. Absent unless the script's
      # frontmatter names one.
      docs = fields.docs or null;
      # The interpreter a Python script's shebang is patched against.
      # `runtimeInputs` cannot serve this purpose: it builds a PATH, and an
      # `import` never consults PATH -- the kernel jumps straight at the
      # interpreter named in the shebang, whose sys.path was fixed when that
      # interpreter was built. Bare python3 unless the script asks, so the
      # withPackages environment is built only for the scripts that import
      # something.
      pythonPackagesRaw = splitWords (fields.pythonPackages or "");
      resolvePythonPkg =
        token:
        if hasPrefix "@" token then
          let
            pname = lib.substring 1 (lib.stringLength token) token;
          in
          siblingExtras.${pname} or (throw "script-discovery: unknown sibling python package @${pname}")
        else
          attrByPath (splitString "." token)
            (throw "script-discovery: pkgs.python3Packages.${token} does not exist")
            pkgs.python3Packages;
      pythonInterpreter =
        if pythonPackagesRaw == [ ] then
          pkgs.python3
        else
          pkgs.python3.withPackages (_ps: map resolvePythonPkg pythonPackagesRaw);
      patchedScript =
        pkgs.runCommand "${name}-script"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pythonInterpreter
              pkgs.zsh
            ];
          }
          ''
            install -Dm755 ${
              # A bare ${filePath} references the file INSIDE the whole
              # flake-source store copy, so the derivation hash was a
              # function of the entire tree: every packaged script rebuilt
              # on any tracked-file edit, and none ever hit cache across
              # commits. builtins.path copies just this file, pinning the
              # hash to the script's own bytes.
              builtins.path {
                path = filePath;
                name = "${name}-source";
              }
            } "$out"
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
      inherit
        description
        runtimeInputs
        tier
        docs
        ;
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
