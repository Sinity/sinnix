# AT-SPI2 Accessibility-Tree Capture
#
# Listens for AT-SPI2 focus-changed / text-changed events across every
# running accessibility-exposed application and periodically dumps the
# accessible subtree (roles/names/text) of the currently focused top-level
# window -- bounded to that one window, not a full-desktop walk. This is the
# structured-text capture lane: prefer the accessibility tree's already-typed
# text over OCR-ing screenshots wherever the tree is populated.
#
# pygobject3 is NOT a propagated runtime dependency of nixpkgs' pyatspi
# (at-spi2-core is only a buildInput), so pkgs/sinnix-capture-a11y/pkg.nix
# lists both explicitly.
#
# Hard runtime dependency: pyatspi can only connect once the AT-SPI2
# accessibility bus (org.a11y.Bus) is registered on the session D-Bus. NixOS
# ships that off by default and, when off, sets `NO_AT_BRIDGE=1`/
# `GTK_A11Y=none` session-wide -- actively telling GTK/Qt apps not to expose
# an accessibility tree at all. This module flips
# `services.gnome.at-spi2-core.enable` on, gated behind `cfg.enable`.
#
# Toolkit opt-in: a running bus is necessary but not sufficient, because each
# toolkit decides separately whether to publish a tree. Chrome-family apps
# need `--force-renderer-accessibility` (set on the Chrome wrapper's
# `commandLineArgs` in modules/features/desktop/browser.nix) and Qt needs
# `QT_LINUX_ACCESSIBILITY_ALWAYS_ON` (set below). Without those the registry
# root sits at ChildCount=0 and the lane records nothing while every unit
# involved reports healthy.
{
  mkServiceModule,
  mkCaptureLane,
  config,
  lib,
  helpers,
  pkgs,
  ...
}@args:
let
  username = config.sinnix.user.name;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  a11yDaemon = scriptPkgs.sinnix-capture-a11y;
  capturesRoot = config.sinnix.paths.activityRoot;
  laneDir = "${capturesRoot}/a11y";
  cfg = config.sinnix.services.capture-a11y;
in
mkServiceModule (mkCaptureLane {
  name = "capture-a11y";
  description = "AT-SPI2 accessibility-tree capture (focus/text-changed events + focused-window subtree dumps)";
  inherit username laneDir;
  mode = "stream";
  captureName = "a11y";
  eventDriven = true;
  # Event-driven, not cadence-based: a daily budget so a day with the
  # desktop asleep/idle doesn't false-positive stale.
  staleAfterSeconds = 86400;
  # A day-long staleness budget cannot notice the real failure mode -- unit
  # healthy, listeners registered, but registry root at ChildCount=0, so the
  # lane is structurally guaranteed to stay silent. Poll the registry root
  # on the sentinel's 1-minute cadence instead: exit 0 when something is
  # published, exit 1 when the bus answers with ChildCount 0
  # (confirmed-absent publisher), exit 3 for anything the probe cannot tell
  # (missing socket, busctl error, non-numeric reply, timeout) so it reports
  # unknown, never healthy.
  livenessProbe = {
    command = lib.concatStringsSep "; " [
      "uid=$(id -u ${username} 2>/dev/null) || exit 3"
      # at-spi-bus-launcher names this socket "bus"; the "bus_0" spelling
      # belongs to the per-display launcher shape and does not exist here,
      # so the probe could never find the socket and reported unknown
      # forever (observed 2026-08-14: the lane was capturing normally while
      # its own liveness probe exited 3 on every sweep). Accept either
      # rather than pinning the spelling.
      "bus=/run/user/$uid/at-spi/bus"
      "[ -S \"$bus\" ] || bus=/run/user/$uid/at-spi/bus_0"
      "[ -S \"$bus\" ] || exit 3"
      "reply=$(busctl --user --address=\"unix:path=$bus\" call org.a11y.atspi.Registry /org/a11y/atspi/accessible/root org.freedesktop.DBus.Properties Get ss org.a11y.atspi.Accessible ChildCount 2>/dev/null) || exit 3"
      "count=$(printf '%s' \"$reply\" | awk '{print $NF}')"
      "[ -n \"$count\" ] || exit 3"
      "case \"$count\" in *[!0-9]*) exit 3 ;; esac"
      "[ \"$count\" -gt 0 ] && exit 0 || exit 1"
    ];
    timeoutSeconds = 5;
  };
  startLimit = {
    intervalSec = 300;
    burst = 5;
  };
  wantedBy = [ "default.target" ];
  umask = "0077";
  execStart = lib.concatStringsSep " " [
    "${a11yDaemon}/bin/sinnix-capture-a11y"
    "--capture-root ${capturesRoot}"
    "--subtree-interval-seconds ${toString cfg.subtreeIntervalSeconds}"
    "--text-debounce-seconds ${toString cfg.textDebounceSeconds}"
    "--max-depth ${toString cfg.maxDepth}"
    "--max-nodes ${toString cfg.maxNodes}"
  ];
  # gi.repository.Atspi/Atk typelibs aren't a propagated runtime dependency
  # of nixpkgs' pyatspi, and pyatspi's __init__.py unconditionally imports
  # gi.repository.DBus, whose typelib ships in gobject-introspection rather
  # than at-spi2-core. Both directories must be on GI_TYPELIB_PATH or the
  # daemon crash-loops with ImportError before reaching pyatspi code.
  environment = [
    "GI_TYPELIB_PATH=${pkgs.at-spi2-core}/lib/girepository-1.0:${pkgs.gobject-introspection}/lib/girepository-1.0"
  ];
  # The org.a11y.Bus activation file and GTK_A11Y/NO_AT_BRIDGE env vars only
  # apply at graphical-session START, not on a systemd --user daemon-reload.
  # In a session predating the option flip libatspi's _atspi_bus() treats
  # "no accessibility bus" as fatal (g_log abort -> SIGABRT, not a
  # catchable Python exception), so the daemon crashes until relogin;
  # StartLimit bounds the restart storm meanwhile.
  extraConfig = _: {
    services.gnome.at-spi2-core.enable = true;

    # Enabling the bus is necessary but not sufficient: toolkits still have
    # to be told to publish a tree, or the registry root stays at
    # ChildCount=0 and the lane writes nothing while every unit looks
    # healthy.
    #
    # Qt publishes only when asked; GTK3/4 follow the bus once NO_AT_BRIDGE
    # and GTK_A11Y=none are absent (NixOS sets those two only while
    # at-spi2-core is disabled, so flipping it above is enough there).
    # Chrome/Electron additionally need --force-renderer-accessibility, set
    # on the Chrome wrapper in modules/features/desktop/browser.nix.
    #
    # These are session variables, so already-running applications keep the
    # environment they were launched with -- the lane goes live for a given
    # app only once it restarts under a session that has these set.
    environment.sessionVariables = {
      QT_LINUX_ACCESSIBILITY_ALWAYS_ON = "1";
      ACCESSIBILITY_ENABLED = "1";
    };
  };
  extraOptions = {
    subtreeIntervalSeconds = lib.mkOption {
      type = lib.types.int;
      default = 30;
      description = "Minimum seconds between periodic focused-window accessible-subtree dumps.";
    };
    textDebounceSeconds = lib.mkOption {
      type = lib.types.float;
      default = 2.0;
      description = "Minimum seconds between accepted text-changed records for the same accessible object (coalesces keystroke-rate event bursts).";
    };
    maxDepth = lib.mkOption {
      type = lib.types.int;
      default = 40;
      description = "Maximum subtree walk depth for the periodic focused-window dump.";
    };
    maxNodes = lib.mkOption {
      type = lib.types.int;
      default = 2000;
      description = "Maximum node count per periodic focused-window subtree dump (bounds pathological trees, e.g. Chromium's full-DOM-as-AT-SPI rendering).";
    };
  };
}) args
