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
#
# Co-locating dotfile declarations on the owning capability replaces the
# previous pattern where each feature wired its own `xdg.configFile` blocks
# inside `home-manager.users.<user>` lambdas. See dots/attic finding (2026-
# 05-24): there are no truly orphan top-level dots/ subdirs; every active
# subdir is consumed by some default-on feature via `mkDotsFile "/X/..."`.
{
  config,
  lib,
  ...
}:
let
  user = config.sinnix.user.name;
  dotsRoot = config.sinnix.paths.dotsRoot;

  hasDotfileMeta =
    cap:
    (cap.enable or false) && (cap ? meta) && (cap.meta ? dotfiles) && (cap.meta.dotfiles or { }) != { };

  # Two-level walk of features.<domain>.<name>
  featureCaps = lib.concatMap (domain: lib.attrValues (config.sinnix.features.${domain} or { })) (
    builtins.attrNames (config.sinnix.features or { })
  );

  # One-level walk of services.<name>
  serviceCaps = lib.attrValues (config.sinnix.services or { });

  eligible = builtins.filter hasDotfileMeta (featureCaps ++ serviceCaps);

  # Merge declarations from every eligible capability into a single attrset
  # per HM target (configFile / dataFile). Right-most cap wins on collision;
  # the byte-diff verification in Phase 7c catches accidental overwrites.
  mergeSlot = slot: lib.foldl' (acc: cap: acc // (cap.meta.dotfiles.${slot} or { })) { } eligible;

  configFileEntries = mergeSlot "configFile";
  dataFileEntries = mergeSlot "dataFile";
  homeFileEntries = mergeSlot "homeFile";

  # Defaults match HM's own option defaults for xdg.configFile / xdg.dataFile.
  # `recursive = false` means "treat <source> as a single symlink target";
  # opt into per-file recursion explicitly via the attrset form when needed.
  defaults = {
    recursive = false;
    force = false;
  };
  normalize = v: if builtins.isString v then defaults // { source = v; } else defaults // v;
in
{
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
        };
    in
    {
      xdg.configFile = lib.mapAttrs (_n: renderEntry) configFileEntries;
      xdg.dataFile = lib.mapAttrs (_n: renderEntry) dataFileEntries;
      home.file = lib.mapAttrs (_n: renderEntry) homeFileEntries;
    };
}
