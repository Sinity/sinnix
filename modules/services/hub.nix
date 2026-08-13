# Sinnix hub — the operator's browser front door to the estate, reachable from
# the tailnet and nowhere else.
#
# Three units, all in the user manager, all default-off until a host opts in:
#
#   sinnix-hub.service          Caddy: static serving + reverse proxying
#   sinnix-hub-render.service   periodic server-side render of the pages
#   sinnix-hub-feedback.service append-only spool for report annotations
#
# ── Why the user manager ────────────────────────────────────────────────────
# The dashboard's whole value is the ops-reducer's current-state snapshot, and
# the reducer is a *user* service whose Unix socket is 0600-owned by the
# operator. Running the hub in the same manager lets it reach that socket, the
# operator-owned reports tree, and the reducer's bounded action API without
# loosening a single permission. Nothing here needs a privileged port.
#
# ── Why it cannot be seen from the LAN ──────────────────────────────────────
# Two independent layers, either of which alone would suffice:
#
#  1. Binding. Caddy is told to listen on exactly two addresses: loopback, and
#     the host's tailscale0 IPv4 address. Never 0.0.0.0. The tailnet address is
#     not known at build time and is not a repository-publishable fact, so an
#     ExecStartPre resolves it from the interface itself (not `tailscale ip`,
#     which needs the privileged tailscaled socket) and writes it to an
#     environment file the Caddyfile interpolates. It retries while the
#     interface comes up and fails the unit if it never does — a hub that
#     cannot bind the tailnet is supposed to be down, not listening wider.
#
#  2. Firewall. `sinnix.services.tailscale.useRoutingFeatures = "none"` means
#     upstream does *not* put tailscale0 in trustedInterfaces, so the ports are
#     opened per-interface on tailscale0 only. A LAN peer is dropped by the
#     firewall before it reaches a socket that was never bound for it anyway.
#
# ── Why there is no second control plane ────────────────────────────────────
# Every button on every page posts to the ops-reducer's existing action API
# through a reverse-proxied path. That API owns admission (targets must be
# attested runtime-inventory units, attested agent jobs, or name-shaped
# live-verified `sinnix-scope` transient scopes — sinnix-pl37), optimistic
# concurrency (expected_revision), idempotency keys, and receipts. The hub adds
# no shell-out, no sudo, and no privileged helper: it is a view over a contract
# that already existed. Where the contract still cannot express something (a
# scope can be stopped but has no service definition to restart) the page says
# so instead of growing a private kill path.
{
  mkServiceModule,
  config,
  lib,
  pkgs,
  helpers,
  ...
}@args:
let
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  userName = config.sinnix.user.name;
in
mkServiceModule {
  name = "hub";
  description = "Tailnet-only web hub: reports, estate dashboard, AI control panel";

  surface = {
    unit = "sinnix-hub.service";
    manager = "user";
    resourceClass = "interactive-agent";
    observe = {
      enable = true;
      restartable = true;
    };
  };

  extraOptions = {
    port = lib.mkOption {
      type = lib.types.port;
      default = 8880;
      description = "Port the hub itself listens on, on loopback and the tailnet address.";
    };

    stateDir = lib.mkOption {
      type = lib.types.str;
      default = "/realm/state/sinnix-hub";
      description = ''
        Directory holding the rendered pages and Caddy's own scratch state.
        Lives on the /realm NVMe volume rather than the wear-limited root, and
        holds nothing that is not regenerated on the next render.
      '';
    };

    reportsDir = lib.mkOption {
      type = lib.types.str;
      default = "/realm/data/derived/reports";
      description = "Directory of generated HTML reports served under /reports/.";
    };

    feedbackDir = lib.mkOption {
      type = lib.types.str;
      default = "/realm/data/derived/hub-feedback";
      description = ''
        Spool directory for report annotations posted to /feedback. One
        append-only JSONL file per UTC day; agents read it directly.
      '';
    };

    renderIntervalSeconds = lib.mkOption {
      type = lib.types.int;
      default = 60;
      description = "How often the dashboard and AI panel are re-rendered.";
    };

    aiServices = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [
        "whisper"
        "tts"
        "ollama"
        "litellm"
        "llama-cpp"
        "koboldcpp"
        "comfyui"
        "musicgen"
        "ocr"
        "open-webui"
      ];
      description = ''
        Names of AI services the control panel offers. Names only: every unit,
        endpoint, idle timeout, admission key, and restartable flag is resolved
        at render time from /etc/sinnix/runtime-inventory.json, so the panel
        cannot drift from the inventory the action API validates against. A
        name with no registered surface renders as "not registered" rather
        than disappearing.
      '';
    };

    frontends = lib.mkOption {
      default = {
        open-webui = {
          label = "Open WebUI";
          port = 8881;
          upstream = "127.0.0.1:8080";
        };
        comfyui = {
          label = "ComfyUI";
          port = 8882;
          upstream = "127.0.0.1:8188";
        };
        koboldcpp = {
          label = "KoboldCpp";
          port = 8883;
          upstream = "127.0.0.1:5001";
        };
      };
      description = ''
        Loopback web UIs republished on the tailnet, keyed by the
        `sinnix.services.<name>` that owns them; entries whose service is
        disabled are skipped.

        Each gets its own port with the proxy rooted at `/` rather than a
        subpath of the hub. That is deliberate: these are single-page apps that
        emit absolute asset URLs and have no base-path support, so a
        `/ui/comfyui/` mount would half-work in a way that wastes an
        afternoon. One port each costs one firewall entry and always works.
      '';
      type = lib.types.attrsOf (
        lib.types.submodule {
          options = {
            label = lib.mkOption {
              type = lib.types.str;
              description = "Human-facing name shown on the dashboard.";
            };
            port = lib.mkOption {
              type = lib.types.port;
              description = "Tailnet-facing port for this frontend.";
            };
            upstream = lib.mkOption {
              type = lib.types.str;
              description = "host:port of the loopback service being republished.";
            };
          };
        }
      );
    };
  };

  configFn =
    { cfg, ... }:
    let
      tailscaleInterface = config.sinnix.services.tailscale.interfaceName;
      wwwDir = "${cfg.stateDir}/www";

      # Only republish a frontend whose owning service is actually enabled.
      activeFrontends = lib.filterAttrs (
        name: _: (config.sinnix.services.${name} or { }).enable or false
      ) cfg.frontends;

      manifest = pkgs.writeText "sinnix-hub-manifest.json" (
        builtins.toJSON {
          schema = "sinnix-hub-manifest-v1";
          host = config.networking.hostName;
          inherit (cfg) port aiServices;
          reportsDir = cfg.reportsDir;
          feedbackDir = cfg.feedbackDir;
          frontends = lib.mapAttrsToList (name: frontend: {
            inherit name;
            inherit (frontend) label port upstream;
          }) activeFrontends;
          # The pages themselves are reachable from the nav on every page, so
          # this list is only the things a link is the *only* way to reach.
          links = [
            {
              label = "Ops snapshot (JSON)";
              href = "/ops/v1/snapshot";
              note = "the reducer's current-state document";
            }
            {
              label = "Action receipts (JSON)";
              href = "/ops/v1/receipts";
              note = "what was done through the hub, and by whom it was refused";
            }
          ];
        }
      );

      # The reverse-proxy targets live in the operator's runtime directory,
      # whose path depends on a uid this module has no business hardcoding.
      # systemd expands %t for the units; Caddy expands {$VAR} in its own
      # config text, so the units hand the same directory to both and neither
      # side needs the uid at evaluation time.
      opsSocket = "{$SINNIX_HUB_RUNTIME}/sinnix/ops.sock";
      feedbackSocket = "{$SINNIX_HUB_RUNTIME}/sinnix/hub-feedback.sock";

      frontendSites = lib.concatStringsSep "\n" (
        lib.mapAttrsToList (_name: frontend: ''
          http://:${toString frontend.port} {
            bind {$SINNIX_HUB_TAILNET_IP} 127.0.0.1
            reverse_proxy ${frontend.upstream}
          }
        '') activeFrontends
      );

      # Caddy warns on every start about non-canonical formatting, and the
      # canonical form is tab-indented -- unreadable to write inside a Nix
      # indented string. Normalise at build time instead, so the deployed file
      # is always fmt-clean and the source here stays legible.
      caddyfile = pkgs.runCommand "sinnix-hub.Caddyfile" { } ''
        cp ${rawCaddyfile} "$out"
        chmod +w "$out"
        ${pkgs.caddy}/bin/caddy fmt --overwrite "$out"
      '';

      rawCaddyfile = pkgs.writeText "sinnix-hub.Caddyfile.raw" ''
        {
          admin off
          auto_https off
          persist_config off
          log {
            output stderr
            format console
            level ERROR
          }
        }

        (hub) {
          redir /reports /reports/
          handle_path /reports/* {
            root * ${cfg.reportsDir}
            file_server browse
          }

          # Same-origin gate on the action API. A browser sends Origin on POST
          # even same-origin, so this cannot be a blanket "reject any Origin";
          # it rejects any Origin that is not one of the hub's own. Together
          # with the reducer's expected_revision check -- which needs a prior
          # read that CORS denies cross-origin -- a blind cross-site POST has
          # nothing to work with.
          handle_path /ops/* {
            @crossOrigin {
              header Origin *
              not header Origin http://{$SINNIX_HUB_TAILNET_IP}:${toString cfg.port}
              not header Origin http://127.0.0.1:${toString cfg.port}
              not header Origin http://localhost:${toString cfg.port}
            }
            respond @crossOrigin "cross-origin request refused" 403
            reverse_proxy unix/${opsSocket}
          }

          handle_path /feedback* {
            reverse_proxy unix/${feedbackSocket}
          }

          handle {
            root * ${wwwDir}
            file_server
          }
        }

        # `bind` is load-bearing, not decoration. Listing two site addresses
        # (http://<tailnet>:PORT, http://127.0.0.1:PORT) does NOT produce two
        # listeners: Caddy merges same-port sites into one server listening on
        # :PORT -- i.e. 0.0.0.0 -- and separates them by Host header, which is
        # no boundary at all. `bind` sets the socket addresses explicitly, so
        # the listeners really are the tailnet address and loopback.
        # Verify after any edit here with:
        #   caddy adapt | jq '.apps.http.servers | map_values(.listen)'
        http://:${toString cfg.port} {
          bind {$SINNIX_HUB_TAILNET_IP} 127.0.0.1
          import hub
        }

        ${frontendSites}
      '';

      # $1 is the environment file to write (the unit passes %t-derived path).
      resolveBind = pkgs.writeShellScript "sinnix-hub-resolve-bind" ''
        set -euo pipefail
        target="$1"
        ${pkgs.coreutils}/bin/mkdir -p "$(${pkgs.coreutils}/bin/dirname "$target")"
        for _ in $(${pkgs.coreutils}/bin/seq 1 60); do
          address="$(${pkgs.iproute2}/bin/ip -4 -o addr show dev ${tailscaleInterface} 2>/dev/null \
            | ${pkgs.gawk}/bin/awk '{print $4}' \
            | ${pkgs.coreutils}/bin/cut -d/ -f1 \
            | ${pkgs.coreutils}/bin/head -n1)"
          if [ -n "''${address:-}" ]; then
            ${pkgs.coreutils}/bin/printf 'SINNIX_HUB_TAILNET_IP=%s\n' "$address" > "$target"
            exit 0
          fi
          ${pkgs.coreutils}/bin/sleep 2
        done
        echo "sinnix-hub: ${tailscaleInterface} has no IPv4 address; refusing to start" >&2
        exit 1
      '';
    in
    {
      assertions = [
        {
          assertion = config.sinnix.services.tailscale.enable;
          message = ''
            sinnix.services.hub requires sinnix.services.tailscale.enable — the
            tailnet is the hub's only security boundary, and the unit binds the
            tailscale interface address. Enabling the hub without it would
            leave a control panel with no boundary at all.
          '';
        }
        {
          assertion =
            let
              ports = [ cfg.port ] ++ (lib.mapAttrsToList (_: f: f.port) cfg.frontends);
            in
            lib.length (lib.unique ports) == lib.length ports;
          message = "sinnix.services.hub: the hub port and every frontend port must be distinct.";
        }
      ];

      # Per-interface, not networking.firewall.allowedTCPPorts: tailscale0 is
      # not a trusted interface under useRoutingFeatures = "none", so this is
      # the only place these ports are reachable from.
      networking.firewall.interfaces.${tailscaleInterface}.allowedTCPPorts = [
        cfg.port
      ]
      ++ lib.mapAttrsToList (_: frontend: frontend.port) activeFrontends;

      systemd.tmpfiles.rules = [
        "d ${cfg.stateDir} 0755 ${userName} users -"
        "d ${wwwDir} 0755 ${userName} users -"
        "d ${cfg.feedbackDir} 0755 ${userName} users -"
      ];

      environment.systemPackages = [
        scriptPkgs.sinnix-hub-render
        scriptPkgs.sinnix-hub-feedback
      ];

      sinnix.runtime.surfaces = {
        hub-feedback = {
          unit = "sinnix-hub-feedback.service";
          manager = "user";
          resourceClass = "interactive-agent";
          observe = {
            enable = true;
            restartable = true;
          };
        };
        hub-render = {
          unit = "sinnix-hub-render.timer";
          kind = "timer";
          manager = "user";
          resourceClass = "background-maintenance";
          observe = {
            enable = true;
            restartable = true;
          };
        };
      };

      home-manager.users.${userName} = {
        home.packages = [
          scriptPkgs.sinnix-hub-render
          scriptPkgs.sinnix-hub-feedback
        ];

        systemd.user.services.sinnix-hub = {
          Unit = {
            Description = "Sinnix tailnet hub (Caddy)";
            After = [ "sinnix-hub-feedback.service" ];
            Wants = [
              "sinnix-hub-feedback.service"
              "sinnix-hub-render.timer"
            ];
          };
          Service = {
            Type = "simple";
            # Resolves the tailnet address into the environment file the
            # Caddyfile interpolates. systemd re-reads EnvironmentFile for each
            # exec, so ExecStart sees what ExecStartPre just wrote.
            ExecStartPre = "${resolveBind} %t/sinnix/hub-bind.env";
            # The leading `-` is load-bearing: systemd loads EnvironmentFile
            # before running ExecStartPre, so without it the unit dies on a
            # cold start ("Failed to load environment files") having never
            # spawned the step that creates the file. Marked optional, the
            # pre-step writes it and ExecStart's own re-read picks it up.
            EnvironmentFile = "-%t/sinnix/hub-bind.env";
            Environment = [
              "XDG_DATA_HOME=${cfg.stateDir}/caddy"
              "SINNIX_HUB_RUNTIME=%t"
            ];
            ExecStart = "${pkgs.caddy}/bin/caddy run --config ${caddyfile} --adapter caddyfile";
            ExecReload = "${pkgs.caddy}/bin/caddy reload --config ${caddyfile} --adapter caddyfile";
            Restart = "on-failure";
            RestartSec = "5s";
            NoNewPrivileges = true;
            UMask = "0077";
          };
          Install.WantedBy = [ "default.target" ];
        };

        systemd.user.services.sinnix-hub-feedback = {
          Unit.Description = "Sinnix hub annotation spool endpoint";
          Service = {
            Type = "simple";
            ExecStart = lib.concatStringsSep " " [
              "${scriptPkgs.sinnix-hub-feedback}/bin/sinnix-hub-feedback"
              "--socket %t/sinnix/hub-feedback.sock"
              "--spool-dir ${cfg.feedbackDir}"
            ];
            Restart = "on-failure";
            RestartSec = "5s";
            NoNewPrivileges = true;
            UMask = "0022";
          };
          Install.WantedBy = [ "default.target" ];
        };

        systemd.user.services.sinnix-hub-render = {
          Unit.Description = "Render the Sinnix hub dashboard and AI control panel";
          Service = {
            Type = "oneshot";
            # /run/current-system/sw/bin carries systemctl and nvidia-smi; the
            # script's own runtimeInputs are prefixed ahead of it by the wrapper.
            Environment = [ "PATH=/run/wrappers/bin:/run/current-system/sw/bin" ];
            ExecStart = lib.concatStringsSep " " [
              "${scriptPkgs.sinnix-hub-render}/bin/sinnix-hub-render"
              "--manifest ${manifest}"
              "--out ${wwwDir}"
            ];
            NoNewPrivileges = true;
          };
        };

        systemd.user.timers.sinnix-hub-render = {
          Unit.Description = "Periodic re-render of the Sinnix hub pages";
          Timer = {
            OnStartupSec = "5s";
            OnUnitActiveSec = "${toString cfg.renderIntervalSeconds}s";
            AccuracySec = "5s";
          };
          Install.WantedBy = [ "timers.target" ];
        };
      };
    };
} args
