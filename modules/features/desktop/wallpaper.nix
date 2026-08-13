# Wallpaper corpus, CLI, and time-of-day set switching for Noctalia.
#
# Noctalia is the Material-You color authority (wallpaper -> palette ->
# GTK/Qt/kitty/etc templates -> Hyprland border colors, see noctalia.nix); the
# active wallpaper is not decoration here, it drives the whole system palette.
# This module owns everything AROUND that pipeline without fighting it:
#
#   - a curated corpus at `corpusRoot` (default /realm/media/wallpaper, off
#     the wear-limited root SSD, alongside the lake's other media
#     collections) organized as sets/<mood>/{dark,light} + a flat pool/ for
#     imported-but-unclassified images + generated/ for the opt-in
#     ComfyUI lane (see modules/services/wallpaper-generate.nix);
#   - Noctalia v5's native per-mode wallpaper directories
#     (config.toml: wallpaper.directory_dark / directory_light -- verified
#     against the installed noctalia-5.0.0 binary's own config schema
#     validator, not assumed) pointed at STABLE paths under ~/wallpaper
#     (already the live, persisted, Noctalia-watched directory -- see
#     modules/persistence.nix) so config.toml itself never needs to change;
#   - a small time-of-day timer that retargets the ~/wallpaper/{dark,light}
#     symlinks to sets/<mood>/{dark,light} every 15 minutes. Noctalia v5 has
#     no native time-of-day wallpaper scheduling (verified: exhaustive in the
#     shipped binary's `noctalia msg --help` command list has no such verb),
#     so this is external, and deliberately does NOT touch config.toml --
#     only the symlink targets move, so Noctalia's own Settings GUI can keep
#     writing config.toml without racing this timer;
#   - the `sinnix-wallpaper` CLI (current/next/prev/pin/unpin/import/status)
#     wired over Noctalia's real IPC surface (`noctalia msg wallpaper-*`,
#     `color-scheme-get`, `theme-mode-get` -- verified against the shipped
#     binary's `noctalia msg --help`) plus the offline `noctalia theme`
#     palette-preview subcommand.
#
# OLED care (this is the FO48U, not a theory exercise): the time-of-day sets
# exist so the operator can bias toward LOW-KEY, high-contrast imagery for
# long-dwell modes (day/night) and reserve brighter imagery for
# shorter-lived morning/evening windows; `sinnix-wallpaper import` runs a
# brightness/uniformity heuristic (ImageMagick mean + stddev on a downscaled
# grayscale render) and warns -- but does not block -- on images with large,
# low-contrast bright regions, which are the OLED burn-in risk shape.
# Animated wallpaper (mpvpaper) is deliberately NOT wired here: the sibling
# research flagged it risk-first for this panel and the default is to skip
# it entirely, not to gate it behind an option nobody asked for.
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
      default = "/realm/media/wallpaper";
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
      # Every ancestor needs its own rule, and ancestors must come first.
      # `sets` was previously undeclared, so tmpfiles created it implicitly as
      # root inside a sinity-owned parent and then refused every leaf below it:
      # "Detected unsafe path transition /realm/media/wallpaper (owned by
      # sinity) -> /realm/media/wallpaper/sets (owned by root)". The timer has
      # been firing into missing directories and exiting 0 ever since.
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
