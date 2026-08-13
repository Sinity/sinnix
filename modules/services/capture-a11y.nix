# AT-SPI2 Accessibility-Tree Capture
#
# Listens for AT-SPI2 focus-changed / text-changed events across every
# running accessibility-exposed application and periodically dumps the
# accessible subtree (roles/names/text) of the currently focused top-level
# window -- bounded to that one window, not a full-desktop walk. This is the
# structured-text capture lane from sinnix-9pd's "structured beats pixels,
# cuts later OCR load" design: prefer the accessibility tree's already-typed
# text over OCR-ing screenshots wherever the tree is populated.
#
# Binding choice: nixpkgs packages `python3Packages.pyatspi` (2.58.1,
# "Python client bindings for D-Bus AT-SPI"), the modern successor to the
# old standalone pyatspi2 -- confirmed present on this flake's pinned
# nixpkgs, so no gi.repository.Atspi hand-rolling was needed. pyatspi is
# itself built on pygobject3/gi.repository.Atspi (at-spi2-core is a
# buildInput of nixpkgs' pyatspi derivation), but pygobject3 is NOT a
# propagated runtime dependency of pyatspi -- pkgs/sinnix-capture-a11y/pkg.nix
# lists both explicitly.
#
# Hard runtime dependency: pyatspi can only connect once the AT-SPI2
# accessibility bus (org.a11y.Bus) is actually registered on the session
# D-Bus. NixOS ships that off by default (`services.gnome.at-spi2-core.enable
# = false`) and, when off, sets `NO_AT_BRIDGE=1`/`GTK_A11Y=none` session-wide
# -- actively telling GTK/Qt apps not to expose an accessibility tree at all
# (nixpkgs' nixos/modules/services/desktops/gnome/at-spi2-core.nix). This
# module flips that on whenever capture-a11y itself is enabled (gated behind
# `cfg.enable` via mkServiceModule, so it has no effect when the lane is
# off).
#
# Toolkit opt-in: a running bus is necessary but not sufficient, because each
# toolkit decides separately whether to publish a tree. Chrome-family apps
# need `--force-renderer-accessibility` (now set on the Chrome wrapper's
# `commandLineArgs` in modules/features/desktop/browser.nix) and Qt needs
# `QT_LINUX_ACCESSIBILITY_ALWAYS_ON` (set below). Without those the registry
# root sits at ChildCount=0 and the lane records nothing while every unit
# involved reports healthy -- which is exactly how it ran for its first day.
{
  mkServiceModule,
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
  inherit (config.sinnix.paths) capturesRoot;
  laneDir = "${capturesRoot}/a11y";
in
mkServiceModule {
  name = "capture-a11y";
  description = "AT-SPI2 accessibility-tree capture (focus/text-changed events + focused-window subtree dumps)";
  surface = {
    unit = "sinnix-capture-a11y.service";
    manager = "user";
    # No explicit `kind`: this is a real owned systemd .service unit (the
    # daemon below), so it defaults to "service" like every other daemon
    # surface in the repo. `kind = "capture"` is reserved for surfaces with
    # no real backing unit -- see capture-registry.nix's docstring and
    # terminal-capture.nix (hook-based, no persistent daemon). Getting this
    # wrong silently drops the unit from runtime.nix's OnFailure
    # health-transition wiring (kind == "service" filter).
    resourceClass = "capture-runtime";
    observe = {
      enable = true;
      restartable = true;
    };
    captures = [
      {
        name = "a11y";
        path = laneDir;
        eventDriven = true;
        # Event-driven (focus/text-change activity in any AT-SPI2-exposed
        # app), not cadence-based -- daily budget mirrors terminal-capture's
        # asciinema lane so a day with the desktop asleep/idle doesn't
        # false-positive stale.
        staleAfterSeconds = 86400;
        # sinnix-pev0: staleAfterSeconds alone took up to a full day to
        # notice the actual 2026-08-13 incident (unit healthy, listeners
        # registered, AT-SPI registry root at ChildCount=0 -- no application
        # had published a tree at all, so the lane was structurally
        # guaranteed to stay silent regardless of budget length). Poll the
        # registry root directly on the sentinel's 1-minute cadence instead:
        # exit 0 when something is published, exit 1 when the bus answers
        # but ChildCount is 0 (confirmed-absent publisher), anything else
        # (bus/socket missing, busctl error, non-numeric reply, timeout)
        # means the probe couldn't tell -- reported as unknown, never
        # silently healthy. Query verified live against the running bus
        # 2026-08-13.
        livenessProbe = {
          command = lib.concatStringsSep "; " [
            "uid=$(id -u ${username} 2>/dev/null) || exit 3"
            "bus=/run/user/$uid/at-spi/bus_0"
            "[ -S \"$bus\" ] || exit 3"
            "reply=$(busctl --user --address=\"unix:path=$bus\" call org.a11y.atspi.Registry /org/a11y/atspi/accessible/root org.freedesktop.DBus.Properties Get ss org.a11y.atspi.Accessible ChildCount 2>/dev/null) || exit 3"
            "count=$(printf '%s' \"$reply\" | awk '{print $NF}')"
            "[ -n \"$count\" ] || exit 3"
            "case \"$count\" in *[!0-9]*) exit 3 ;; esac"
            "[ \"$count\" -gt 0 ] && exit 0 || exit 1"
          ];
          timeoutSeconds = 5;
        };
      }
    ];
  };
  configFn =
    { cfg, ... }:
    {
      services.gnome.at-spi2-core.enable = true;

      # Enabling the bus is necessary but not sufficient: toolkits still have
      # to be told to publish a tree. Measured live 2026-08-13 -- the bus,
      # launcher and registryd were all running and the daemon had been up 24h
      # burning CPU, while the registry root reported ChildCount=0. Nothing was
      # exposed, so the lane could never write a byte no matter how healthy
      # every unit looked.
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

      systemd.tmpfiles.rules = [
        "d ${laneDir} 0755 ${username} users -"
      ];

      home-manager.users.${username} = {
        systemd.user.services.sinnix-capture-a11y = {
          Unit = {
            Description = "AT-SPI2 accessibility-tree capture (focus/text-changed events + focused-window subtree dumps)";
            After = [ "graphical-session.target" ];
            PartOf = [ "graphical-session.target" ];
            StartLimitIntervalSec = 300;
            StartLimitBurst = 5;
          };
          Service = lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = config.sinnix.runtime.inventory;
            unit = "sinnix-capture-a11y.service";
            overrides = {
              Type = "simple";
              ExecStart = lib.concatStringsSep " " [
                "${a11yDaemon}/bin/sinnix-capture-a11y"
                "--capture-root ${capturesRoot}"
                "--subtree-interval-seconds ${toString cfg.subtreeIntervalSeconds}"
                "--text-debounce-seconds ${toString cfg.textDebounceSeconds}"
                "--max-depth ${toString cfg.maxDepth}"
                "--max-nodes ${toString cfg.maxNodes}"
              ];
              # gi.repository.Atspi/Atk typelibs aren't a propagated runtime
              # dependency of nixpkgs' pyatspi (at-spi2-core is only a
              # buildInput of *its* derivation) -- point PyGObject at
              # at-spi2-core's typelib directory explicitly. pyatspi's
              # __init__.py also imports gi.repository.DBus at module load
              # time (unconditionally, not lazily) -- that typelib ships in
              # gobject-introspection itself, not at-spi2-core, so both
              # directories must be on GI_TYPELIB_PATH (colon-separated,
              # matching GLib's own search-path convention) or the daemon
              # crash-loops with ImportError before ever reaching pyatspi
              # code. Caught live: switch succeeded, unit registered, but
              # crash-looped (14 restarts) until this fix.
              Environment = [
                "GI_TYPELIB_PATH=${pkgs.at-spi2-core}/lib/girepository-1.0:${pkgs.gobject-introspection}/lib/girepository-1.0"
              ];
              # Caught live 2026-08-12: services.gnome.at-spi2-core.enable=true
              # (above) flips the NixOS-level option, but the org.a11y.Bus
              # D-Bus-activation service file and the GTK_A11Y/NO_AT_BRIDGE
              # session env vars are only applied at graphical-session START
              # (greeter/PAM/session-env, not systemd --user daemon-reload).
              # Until the next login, libatspi's C-level _atspi_bus() treats
              # "no accessibility bus" as fatal (g_log abort -> SIGABRT
              # coredump, not a catchable Python exception), so this crash
              # is expected on the FIRST activation of a session that
              # predates the option flip, self-resolving after a relogin/
              # reboot. StartLimit bounds the restart storm in the meantime
              # instead of coredumping indefinitely.
              Restart = "on-failure";
              RestartSec = "5s";
              NoNewPrivileges = true;
              ProtectSystem = "strict";
              ProtectHome = "read-only";
              ReadWritePaths = [ laneDir ];
              UMask = "0077";
            };
          };
          Install.WantedBy = [ "default.target" ];
        };
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
} args
