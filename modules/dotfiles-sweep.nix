# Dotfile sweep
#
# Walks every enabled capability under `config.sinnix.features.*.*` and
# `config.sinnix.services.*`, collects `meta.dotfiles.{configFile,dataFile}`
# entries, and materializes them as Home Manager `xdg.{configFile,dataFile}`
# symlinks pointing into `${sinnix.paths.dotsRoot}/<rel>`.
#
# Schema:
#   meta.dotfiles.configFile = {
#     "task/taskrc" = "taskwarrior/taskrc";          # string ⇒ simple symlink, recursive=false
#     "nvim" = { source = "nvim"; recursive = true; force = true; };
#   };
#   meta.dotfiles.dataFile = { "task/hooks/on-add.py" = "taskwarrior/hooks/on-add.py"; };
#   meta.dotfiles.homeFile = { ".gemini/skills" = "_ai/skills"; };  # arbitrary $HOME path
#
# String value ⇒ `{ source = <str>; recursive = false; force = false; }` (HM defaults).
# Attrset value ⇒ merged onto the same defaults; only `source` is required.
# The renderer accepts `recursive`, `force`, `onChange`, and `executable`,
# which are the source-backed Home Manager file settings this metadata owns.
{
  config,
  lib,
  ...
}:
let
  user = config.sinnix.user.name;
  dotsRoot = config.sinnix.paths.dotsRoot;
  hm = config.home-manager.users.${user};
  homeDirectory = hm.home.homeDirectory;
  configHome = hm.xdg.configHome;
  dataHome = hm.xdg.dataHome;

  supportedSlots = [
    "configFile"
    "dataFile"
    "homeFile"
  ];
  supportedRendererAttrs = [
    "source"
    "recursive"
    "force"
    "onChange"
    "executable"
  ];
  pathParts = path: builtins.filter (part: part != "" && part != ".") (lib.splitString "/" path);
  canonicalPath = path: "/" + lib.concatStringsSep "/" (pathParts path);

  hasDotfileMeta =
    capability:
    let
      cap = capability.value;
    in
    (cap.enable or false) && (cap ? meta) && (cap.meta ? dotfiles) && (cap.meta.dotfiles or { }) != { };

  featureCaps = lib.concatMap (
    domain:
    lib.mapAttrsToList (name: value: {
      owner = "sinnix.features.${domain}.${name}";
      inherit value;
    }) (config.sinnix.features.${domain} or { })
  ) (builtins.attrNames (config.sinnix.features or { }));

  serviceCaps = lib.mapAttrsToList (name: value: {
    owner = "sinnix.services.${name}";
    inherit value;
  }) (config.sinnix.services or { });

  eligible = builtins.filter hasDotfileMeta (featureCaps ++ serviceCaps);

  slotEntries =
    slot:
    lib.concatMap (
      capability:
      lib.mapAttrsToList (target: spec: {
        inherit (capability) owner;
        inherit slot target spec;
        canonicalTarget = canonicalPath (
          if slot == "configFile" then
            "${configHome}/${target}"
          else if slot == "dataFile" then
            "${dataHome}/${target}"
          else
            "${homeDirectory}/${target}"
        );
      }) (capability.value.meta.dotfiles.${slot} or { })
    ) eligible;

  entries = lib.concatMap slotEntries supportedSlots;
  entriesFor = slot: builtins.filter (entry: entry.slot == slot) entries;
  entriesToAttrs =
    slot: lib.listToAttrs (map (entry: lib.nameValuePair entry.target entry.spec) (entriesFor slot));

  configFileEntries = entriesToAttrs "configFile";
  dataFileEntries = entriesToAttrs "dataFile";
  homeFileEntries = entriesToAttrs "homeFile";

  duplicates = lib.filter (target: lib.count (entry: entry.canonicalTarget == target) entries > 1) (
    lib.unique (map (entry: entry.canonicalTarget) entries)
  );

  unknownSlots = lib.concatMap (
    capability:
    lib.filter (slot: !(lib.elem slot supportedSlots)) (
      builtins.attrNames capability.value.meta.dotfiles
    )
  ) eligible;

  invalidEntries = builtins.filter (
    entry:
    !(builtins.isString entry.spec)
    && (
      !builtins.isAttrs entry.spec
      || !(entry.spec ? source)
      || !builtins.isString entry.spec.source
      || lib.any (name: !(lib.elem name supportedRendererAttrs)) (builtins.attrNames entry.spec)
    )
  ) entries;

  isContainedRelativePath =
    path:
    builtins.isString path
    && pathParts path != [ ]
    && !(lib.hasPrefix "/" path)
    && !(lib.elem ".." (lib.splitString "/" path));
  escapingTargets = builtins.filter (entry: !(isContainedRelativePath entry.target)) entries;
  escapingSources = builtins.filter (
    entry:
    builtins.isString entry.spec && !(isContainedRelativePath entry.spec)
    ||
      builtins.isAttrs entry.spec
      && entry.spec ? source
      && builtins.isString entry.spec.source
      && !(isContainedRelativePath entry.spec.source)
  ) entries;

  # HM's own defaults: `recursive = false` treats <source> as a single symlink
  # target; opt into per-file recursion via the attrset form.
  defaults = {
    recursive = false;
    force = false;
  };
  normalize = v: if builtins.isString v then defaults // { source = v; } else defaults // v;
in
{
  assertions = [
    {
      assertion = duplicates == [ ];
      message =
        "Multiple enabled capabilities claim the same dotfile target: "
        + lib.concatStringsSep ", " (
          map (
            target:
            "${target} ("
            + lib.concatStringsSep ", " (
              map (entry: entry.owner) (builtins.filter (entry: entry.canonicalTarget == target) entries)
            )
            + ")"
          ) duplicates
        );
    }
    {
      assertion = unknownSlots == [ ];
      message = "Unknown dotfile renderer slots: " + lib.concatStringsSep ", " unknownSlots;
    }
    {
      assertion = invalidEntries == [ ];
      message =
        "Dotfile entries must be strings or source-backed declarations using only source, recursive, force, onChange, and executable: "
        + lib.concatStringsSep ", " (
          map (entry: "${entry.owner}:${entry.slot}.${entry.target}") invalidEntries
        );
    }
    {
      assertion = escapingTargets == [ ];
      message =
        "Dotfile targets must stay below their configured Home Manager root: "
        + lib.concatStringsSep ", " (
          map (entry: "${entry.owner}:${entry.slot}.${entry.target}") escapingTargets
        );
    }
    {
      assertion = escapingSources == [ ];
      message =
        "Dotfile sources must stay below sinnix.paths.dotsRoot: "
        + lib.concatStringsSep ", " (
          map (entry: "${entry.owner}:${entry.slot}.${entry.target}") escapingSources
        );
    }
  ];
  home-manager.users.${user} =
    { config, ... }:
    let
      renderEntry =
        spec:
        let
          n = normalize spec;
        in
        {
          source = config.lib.file.mkOutOfStoreSymlink (dotsRoot + "/${n.source}");
          inherit (n) recursive force;
        }
        // lib.optionalAttrs (n ? onChange) { inherit (n) onChange; }
        // lib.optionalAttrs (n ? executable) { inherit (n) executable; };
    in
    {
      xdg.configFile = lib.mapAttrs (_n: renderEntry) configFileEntries;
      xdg.dataFile = lib.mapAttrs (_n: renderEntry) dataFileEntries;
      home.file = lib.mapAttrs (_n: renderEntry) homeFileEntries;
    };
}
