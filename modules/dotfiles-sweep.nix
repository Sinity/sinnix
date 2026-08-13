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

  featureCaps = lib.concatMap (domain: lib.attrValues (config.sinnix.features.${domain} or { })) (
    builtins.attrNames (config.sinnix.features or { })
  );

  serviceCaps = lib.attrValues (config.sinnix.services or { });

  eligible = builtins.filter hasDotfileMeta (featureCaps ++ serviceCaps);

  # Merges every eligible capability's declarations into one attrset per HM
  # target; right-most capability wins on collision.
  mergeSlot = slot: lib.foldl' (acc: cap: acc // (cap.meta.dotfiles.${slot} or { })) { } eligible;

  configFileEntries = mergeSlot "configFile";
  dataFileEntries = mergeSlot "dataFile";
  homeFileEntries = mergeSlot "homeFile";

  # HM's own defaults: `recursive = false` treats <source> as a single symlink
  # target; opt into per-file recursion via the attrset form.
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
