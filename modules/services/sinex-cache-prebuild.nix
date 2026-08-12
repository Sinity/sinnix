# Async pre-build + cachix push for sinex master moves (sinnix-m9v).
#
# The desktop is already sinex's "builder of record": after every successful
# LOCAL `switch`, sinexCachePush (flake/command-registry.nix) publishes the
# freshly activated sinex closure to sinity.cachix.org so REPEAT builds of the
# same input hash substitute instead of recompiling. That covers only the
# steady state -- the FIRST switch after any sinex master bump still pays
# sinex's full local compile cost (8-11.5 GiB peak rustc RSS, historically)
# synchronously, on the interactive critical path.
#
# This timer decouples that: it periodically diffs the sinex input's locked
# revision in the live flake.lock against the last revision this host has
# already prebuilt (see scripts/sinnix-sinex-cache-prebuild). When it has
# moved -- via the routine `update` devshell command, or any other committed
# flake.lock change -- it builds sinex at that exact locked revision under
# sinnix-scope's `nix-build` command class (the same heavy-lease-serialized,
# nix-build.slice-contained path every other heavy build on this host uses)
# and pushes the result to sinity.cachix.org via the same push logic `switch`
# uses (scripts/sinnix-sinex-cache-push). By the time an operator/agent next
# runs an interactive `switch`, the sinex build for that revision is usually
# already substitutable from the cache.
#
# Runs as the operator's systemd --user manager: `nix build` needs no root,
# and the cachix push needs the operator's ~/.config/cachix auth token.
#
# Enable with: sinnix.services.sinex-cache-prebuild.enable = true;
{
  mkServiceModule,
  lib,
  pkgs,
  helpers,
  ...
}@args:
let
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  prebuild = scriptPkgs."sinnix-sinex-cache-prebuild";
in
mkServiceModule {
  name = "sinex-cache-prebuild";
  description = "Async pre-build + cachix push of sinex whenever its pinned input moves";
  extraOptions = {
    onCalendar = lib.mkOption {
      type = lib.types.str;
      default = "*-*-* *:00,15,30,45:00";
      description = ''
        systemd ``OnCalendar`` expression for the flake.lock check. Cheap (a
        couple of jq reads against a local file) when nothing has moved, so a
        frequent cadence is fine -- it just bounds how long a sinex bump can
        sit uncached before an operator's next interactive `switch` would
        otherwise pay for it synchronously.
      '';
    };
  };
  surface = {
    unit = "sinex-cache-prebuild.timer";
    manager = "user";
    kind = "timer";
    resourceClass = "background-maintenance";
    observe = {
      enable = true;
      restartable = false;
    };
  };
  configFn =
    {
      cfg,
      config,
      ...
    }:
    let
      userName = config.sinnix.user.name;
    in
    {
      # Small marker file recording the last sinex revision this host has
      # already prebuilt + pushed; not declaring it wipes the cache-warmth
      # bookkeeping on every reboot and forces a redundant rebuild the first
      # time the timer fires post-boot.
      sinnix.persistence.home.directories = [
        ".local/state/sinnix/sinex-cache-prebuild"
      ];

      home-manager.users.${userName} = {
        systemd.user.services.sinex-cache-prebuild = {
          Unit.Description = "Detect a sinex input bump and pre-build + cache-push it";
          Service = {
            Type = "oneshot";
            ExecStart = "${prebuild}/bin/sinnix-sinex-cache-prebuild --flake-dir ${config.sinnix.paths.projectRoot} --system ${pkgs.stdenv.hostPlatform.system}";
            # The flake.lock diff itself is nearly instant; when it detects a
            # move, this unit's runtime becomes however long the sinex build
            # takes (the build itself runs detached in its own sinnix-scope
            # nix-build.slice scope). Bound generously so a genuinely wedged
            # build still gets reaped, without killing a legitimate multi-GB
            # Rust workspace compile.
            TimeoutStartSec = "2h";
          };
        };

        systemd.user.timers.sinex-cache-prebuild = {
          Unit.Description = "Periodic sinex input-bump check for pre-building + cache-push";
          Timer = {
            OnCalendar = cfg.onCalendar;
            Persistent = true;
            RandomizedDelaySec = "2min";
            Unit = "sinex-cache-prebuild.service";
          };
          Install.WantedBy = [ "timers.target" ];
        };
      };
    };
} args
