# Async pre-build + cachix push for sinex master moves.
#
# sinexCachePush (flake/command-registry.nix) publishes the sinex closure
# after every successful local `switch`, which covers repeat builds of the
# same input hash but leaves the FIRST switch after a sinex bump paying the
# full local compile synchronously on the interactive critical path.
#
# This timer decouples that: it periodically diffs the sinex input's locked
# revision in flake.lock against the last revision this host prebuilt (see
# scripts/sinnix-sinex-cache-prebuild), and on a move builds that exact
# revision through its declared AgentCTL operation and pushes it via
# scripts/sinnix-sinex-cache-push.
#
# The timer submits the operation through the operator's user manager;
# pueue runs the build and cache push under the declared project contract.
{
  mkServiceModule,
  lib,
  pkgs,
  helpers,
  ...
}@args:
let
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
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
  job =
    { cfg, ... }:
    {
      # Unit predates the sinnix- prefix; keep its name.
      unitName = "sinex-cache-prebuild";
      manager = "user";
      description = "Submit the named Sinex cache-prebuild operation";
      execStart = "${scriptPkgs.sinnixd}/bin/agentctl job start sinnix sinex_cache_prebuild";
      serviceConfig = {
        # This unit only performs the local AgentCTL submission. The declared
        # operation owns the actual build's lifecycle and timeout.
        TimeoutStartSec = "1min";
      };
      timer = {
        description = "Periodic sinex input-bump check for pre-building + cache-push";
        onCalendar = cfg.onCalendar;
        persistent = true;
        randomizedDelaySec = "2min";
      };
    };
  configFn = _: {
    # Small marker file recording the last sinex revision this host has
    # already prebuilt + pushed; not declaring it wipes the cache-warmth
    # bookkeeping on every reboot and forces a redundant rebuild the first
    # time the timer fires post-boot.
    sinnix.persistence.home.directories = [
      ".local/state/sinnix/sinex-cache-prebuild"
    ];
  };
} args
