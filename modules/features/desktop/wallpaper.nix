# Wallpaper corpus, CLI, and time-of-day set switching for Noctalia.
#
# Noctalia is the Material-You color authority (wallpaper -> palette ->
# GTK/Qt/kitty templates -> Hyprland border colors, see noctalia.nix), so the
# active wallpaper drives the whole system palette. This module owns the
# corpus and scheduling around that pipeline:
#
#   - a curated corpus at `corpusRoot` (default /realm/library/media/wallpaper, off
#     the wear-limited root SSD) organized as sets/<mood>/{dark,light}, plus a
#     flat pool/ for imported-but-unclassified images and generated/ for the
#     opt-in ComfyUI lane (modules/services/wallpaper-generate.nix);
#   - Noctalia's per-mode wallpaper directories (config.toml:
#     wallpaper.directory_{dark,light}) pointed at STABLE paths under
#     ~/wallpaper (the live, persisted, Noctalia-watched directory) so
#     config.toml itself never needs to change;
#   - a time-of-day timer retargeting the ~/wallpaper/{dark,light} symlinks.
#     Noctalia has no native time-of-day scheduling, so this is external, and
#     it moves only symlink targets — never config.toml, which Noctalia's own
#     Settings GUI writes and would race;
#   - the `sinnix-wallpaper` CLI over Noctalia's IPC surface (`noctalia msg
#     wallpaper-*`, `color-scheme-get`, `theme-mode-get`) plus the offline
#     `noctalia theme` palette preview.
#
# OLED care for the FO48U: the time-of-day sets let long-dwell modes
# (day/night) bias toward low-key, high-contrast imagery; `sinnix-wallpaper
# import` warns (does not block) on large low-contrast bright regions, the
# burn-in risk shape. Animated wallpaper (mpvpaper) is not wired here — it is
# a burn-in risk on this panel.
{
  mkFeatureModule,
  lib,
  pkgs,
  inputs,
  ...
}@args:
mkFeatureModule {
  path = [
    "desktop"
    "wallpaper"
  ];
  description = "Wallpaper corpus, CLI, and time-of-day set switching for Noctalia";
  extraOptions = {
    corpusRoot = lib.mkOption {
      type = lib.types.str;
      default = "/realm/library/media/wallpaper";
      description = ''
        Canonical wallpaper corpus: sets/<mood>/{dark,light} (curated,
        time-of-day x theme-mode), pool/ (imported, not yet classified), and
        generated/ (opt-in ComfyUI batch output before curation). Lives on
        the /realm NVMe media volume, never in the repository -- wallpapers
        are data, not repo content.
      '';
    };
    moods = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [
        "morning"
        "day"
        "evening"
        "night"
      ];
      description = ''
        Time-of-day mood buckets under corpusRoot/sets/. Controls which
        directories get created; the hour boundaries themselves are hardcoded
        in scripts/sinnix-wallpaper-timeofday, so changing this list from the
        default four also means updating that script's mood selection.
      '';
    };
    timeOfDay.onCalendar = lib.mkOption {
      type = lib.types.str;
      default = "*:0/15";
      description = "systemd OnCalendar for the time-of-day set-switch check.";
    };
  };
  configFn =
    {
      cfg,
      config,
      lib,
      pkgs,
      helpers,
      user,
      ...
    }:
    let
      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
      noctaliaPkg = inputs.noctalia.packages.${pkgs.stdenv.hostPlatform.system}.default;
      moodDirs = lib.concatMap (mood: [
        "d ${cfg.corpusRoot}/sets/${mood}/dark 0755 ${user} users -"
        "d ${cfg.corpusRoot}/sets/${mood}/light 0755 ${user} users -"
      ]) cfg.moods;
    in
    {
      # Every ancestor needs its own rule, and ancestors must come first: an
      # undeclared intermediate is created implicitly as root inside a
      # sinity-owned parent, and tmpfiles then refuses every leaf below it
      # ("Detected unsafe path transition ...").
      systemd.tmpfiles.rules = [
        "d ${cfg.corpusRoot} 0755 ${user} users -"
        "d ${cfg.corpusRoot}/sets 0755 ${user} users -"
        "d ${cfg.corpusRoot}/pool 0755 ${user} users -"
        "d ${cfg.corpusRoot}/generated 0755 ${user} users -"
        "d ${cfg.corpusRoot}/generated/rejected 0755 ${user} users -"
      ]
      ++ moodDirs;

      sinnix.runtime.surfaces.wallpaper-timeofday = {
        unit = "sinnix-wallpaper-timeofday.timer";
        manager = "user";
        kind = "timer";
        resourceClass = "background-maintenance";
        observe = {
          enable = true;
          restartable = false;
        };
      };

      environment.systemPackages = [
        scriptPkgs.sinnix-wallpaper
        scriptPkgs.sinnix-wallpaper-timeofday
      ];

      home-manager.users.${user} =
        { ... }:
        {
          home.sessionVariables = {
            SINNIX_WALLPAPER_CORPUS = cfg.corpusRoot;
            SINNIX_WALLPAPER_MOODS = lib.concatStringsSep "," cfg.moods;
          };

          systemd.user.services.sinnix-wallpaper-timeofday = {
            Unit.Description = "Retarget ~/wallpaper/{dark,light} to the current time-of-day set";
            Service = lib.sinnix.mkRuntimeServiceConfig {
              runtimeInventory = config.sinnix.runtime.inventory;
              # The registered surface unit is the *timer*
              # (sinnix-wallpaper-timeofday.timer, kind = "timer"), so
              # `unit =` lookup would throw -- resolve the class's
              # serviceConfig directly instead (same pattern as
              # weechat-log-sealer.nix).
              resourceClass = "background-maintenance";
              overrides = {
                Type = "oneshot";
                Environment = [
                  "SINNIX_WALLPAPER_CORPUS=${cfg.corpusRoot}"
                  "SINNIX_WALLPAPER_MOODS=${lib.concatStringsSep "," cfg.moods}"
                  "SINNIX_NOCTALIA_BIN=${noctaliaPkg}/bin/noctalia"
                ];
                ExecStart = "${scriptPkgs.sinnix-wallpaper-timeofday}/bin/sinnix-wallpaper-timeofday";
              };
            };
          };

          systemd.user.timers.sinnix-wallpaper-timeofday = {
            Unit.Description = "Timer for the time-of-day wallpaper set switch";
            Timer = {
              OnCalendar = cfg.timeOfDay.onCalendar;
              Persistent = true;
              AccuracySec = "1min";
            };
            Install.WantedBy = [ "timers.target" ];
          };
        };
    };
} args
