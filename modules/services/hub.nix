# Sinnix hub — the operator's browser front door to the system, reachable from
# the tailnet and nowhere else.
#
# One unit of its own, in the user manager, default-off until a host opts in:
#
#   sinnix-hub.service          Caddy: static serving + reverse proxying
#
# Everything the hub serves that is not a file on disk -- the pages, the action
# API, the annotation spool -- comes from the ops-reducer over its Unix socket.
#
# ── Why the user manager ────────────────────────────────────────────────────
# The dashboard's whole value is the ops-reducer's current-state snapshot, and
# the reducer is a *user* service whose Unix socket is 0600-owned by the
# operator. Running the hub in the same manager lets it reach that socket, the
# operator-owned reports tree, and the reducer's bounded action API without
# loosening a single permission. Nothing here needs a privileged port.
#
# ── Where the pages come from ───────────────────────────────────────────────
# Caddy serves no HTML of its own beyond /reports/. Every page is rendered on
# request by the ops-reducer, which already holds the state the pages show, and
# Caddy reverse-proxies the page paths to the reducer's Unix socket. Rendering
# on request replaced an earlier design that wrote the same pages to static
# files on a 60-second timer; a page is now as current as the moment it was
# asked for, and there is no window in which the hub describes a system that
# has since moved on.
#
# ── Where annotations go ────────────────────────────────────────────────────
# `/feedback` is a route on that same reducer, writing the same append-only
# JSONL an earlier standalone feedback daemon wrote (same envelope, same
# file-per-UTC-day, same fsync per line -- agents read those files directly).
# Arrival of a `sinnix-elicit-v1` record starts the drain that a 120s timer used
# to run, coalesced so a comparison session refits the model once rather than
# once per tap.
#
# ── Where the terminal views come from ──────────────────────────────────────
# `/terminals/*` is also a route family on that same reducer (sinnix-859p),
# absorbed from an earlier standalone daemon dedicated to terminal views:
# same URLs, same response shapes, same design doctrine (see the reducer's terminals.py
# module docstring). It used to be its own Unix-socket process behind
# `handle_path /terminals/*`; now it falls through the same catch-all
# `handle` below as every page, so kitty's control sockets and the scrollback
# capture files it reads are reached from the one process already running
# under the operator's own uid, not a second one.
#
# Auth is unchanged by that move. The reducer treats its Unix socket as
# authorized (it is 0600 in the operator's runtime dir) and still demands a
# bearer token on its loopback TCP listener, so proxying the page paths through
# the socket exposes exactly what the action API already exposed there and
# nothing more: the same-origin gate below and the reducer's own
# expected_revision check remain the whole admission story for POSTs.
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
  # Where the phone's always-on telemetry push (speech, the app's event
  # mirror) lands, demuxed by the dispatcher's embedded TCP receiver
  # (absorbed from an earlier standalone receiver unit, sinnix-tjqi). Host/
  # device telemetry's subject root, not this module's own reportsDir/
  # feedbackDir -- see modules/foundation.nix.
  phoneLaneRoot = config.sinnix.paths.machineRoot;
  phoneStreamPort = helpers.data.ports.phoneStream;
in
mkServiceModule {
  name = "hub";
  description = "Tailnet-only web hub: reports, system dashboard, AI control panel";

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

    aiServices = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      # Derived, not listed: every enabled sinnix.services entry that declares
      # itself an AI backend (mkAiService's meta.ai marker). The hand-written
      # list this replaces had silently omitted kokoro and muse-glimmer since
      # it was written -- the drift class dies with the second registry.
      # Disabled services no longer appear at all: with nothing to drift, the
      # old "renders as not-registered rather than disappearing" visibility
      # hack has nothing left to reveal.
      default = lib.naturalSort (
        lib.attrNames (
          lib.filterAttrs (
            _: service: (service.enable or false) && (lib.attrByPath [ "meta" "ai" ] null service) != null
          ) config.sinnix.services
        )
      );
      defaultText = lib.literalExpression "every enabled service carrying meta.ai";
      description = ''
        Names of AI services the control panel offers. Names only: every unit,
        endpoint, idle timeout, admission key, and restartable flag is resolved
        at render time from /etc/sinnix/runtime-inventory.json, so the panel
        cannot drift from the inventory the action API validates against.
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
          shadersDir = "${config.sinnix.paths.dotsRoot}/hypr/shaders";
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
      phoneSocket = "{$SINNIX_HUB_RUNTIME}/sinnix/phone-dispatcher.sock";

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
          # Usage evidence for sinnix's own audits (capture doctrine):
          # the global logger above stays at ERROR for Caddy's own
          # diagnostics, so without a dedicated access logger page usage is
          # otherwise unmeasurable.
          log {
            output file ${cfg.stateDir}/access.log {
              roll_size 10mb
              roll_keep 5
            }
            level INFO
          }

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

          # Not handle_path: the reducer routes on `/feedback` itself, and
          # the CORS answer it gives this route (reports are opened off disk
          # as file://, Origin null) is deliberately not given to /ops/*.
          handle /feedback* {
            reverse_proxy unix/${opsSocket}
          }

          # The phone's live plane. Everything it carries also works through
          # the wifi-gated drain, so this route removes a wait rather than
          # enabling a capability -- and the app labels which path each action
          # actually took. Deliberately NOT behind the same-origin gate above:
          # a native client sends no Origin header, and the gate exists to stop
          # a browser on another site from posting here, which is not a shape
          # this route can be reached in.
          handle_path /phone/* {
            reverse_proxy unix/${phoneSocket}
          }

          # The pages themselves. Rendered on request by the ops-reducer from
          # the state it already holds -- no prefix stripping here, unlike
          # /ops/* above: the reducer routes on the page path itself.
          redir /work /work/
          redir /services /services/
          redir /ai /ai/
          redir /shaders /shaders/

          handle {
            reverse_proxy unix/${opsSocket}
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

      # The dispatcher's embedded telemetry receiver binds tailscale0
      # directly (it is a raw TCP listener, not something Caddy fronts), so
      # it needs its own resolved-address file on the dispatcher unit's own
      # ExecStartPre -- ported unchanged from an earlier standalone
      # receiver module.
      resolveBindPhoneStream = pkgs.writeShellScript "sinnix-phone-dispatcher-resolve-bind" ''
        set -euo pipefail
        target="$1"
        ${pkgs.coreutils}/bin/mkdir -p "$(${pkgs.coreutils}/bin/dirname "$target")"
        for _ in $(${pkgs.coreutils}/bin/seq 1 60); do
          address="$(${pkgs.iproute2}/bin/ip -4 -o addr show dev ${tailscaleInterface} 2>/dev/null \
            | ${pkgs.gawk}/bin/awk '{print $4}' \
            | ${pkgs.coreutils}/bin/cut -d/ -f1 \
            | ${pkgs.coreutils}/bin/head -n1)"
          if [ -n "''${address:-}" ]; then
            ${pkgs.coreutils}/bin/printf 'SINNIX_PHONE_STREAM_HOST=%s\n' "$address" > "$target"
            exit 0
          fi
          ${pkgs.coreutils}/bin/sleep 2
        done
        echo "sinnix-phone-dispatcher: ${tailscaleInterface} has no IPv4 address; refusing to start" >&2
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
          assertion = config.sinnix.services.ops-reducer.enable;
          message = ''
            sinnix.services.hub requires sinnix.services.ops-reducer.enable —
            every page except /reports/ is rendered by the reducer on request,
            and every button posts to its action API. Without it the hub is a
            proxy to nothing.
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

      # The pages are rendered by the reducer, which needs the manifest this
      # module owns the content of; so is /feedback, which needs the spool
      # directory and the drain to run when an elicit record lands.
      #
      # The drain runs as a transient unit rather than a child of the reducer:
      # `sinnix-elicit` writes under /realm/data/notes/preferences, which the
      # reducer's own ProtectSystem=strict sandbox has no business opening, and
      # a named transient unit keeps the run visible in the journal under the
      # name the timer used to have.
      sinnix.services.ops-reducer = {
        hubManifest = manifest;
        feedbackDir = cfg.feedbackDir;
        elicitCommand = lib.concatStringsSep " " [
          "systemd-run"
          "--user"
          "--quiet"
          "--collect"
          "--unit=sinnix-elicit-autoingest"
          "${scriptPkgs.sinnix-elicit}/bin/sinnix-elicit"
          "autoingest"
        ];
      };

      # Per-interface, not networking.firewall.allowedTCPPorts: tailscale0 is
      # not a trusted interface under useRoutingFeatures = "none", so this is
      # the only place these ports are reachable from.
      networking.firewall.interfaces.${tailscaleInterface}.allowedTCPPorts = [
        cfg.port
        phoneStreamPort
      ]
      ++ lib.mapAttrsToList (_: frontend: frontend.port) activeFrontends;

      systemd.tmpfiles.rules = [
        "d ${cfg.stateDir} 0755 ${userName} users -"
        "d ${cfg.feedbackDir} 0755 ${userName} users -"
        # Absorbed from an earlier standalone receiver module. The
        # CaptureWriter/SpeechLane ports in the dispatcher script also
        # mkdir(parents=True) these lazily on first write, but declaring them
        # keeps ownership/mode explicit rather than inherited from whatever
        # umask the dispatcher happens to run under.
        "d ${phoneLaneRoot}/phone-speech 0755 ${userName} users -"
        # Raw utterance audio, kept whether or not transcription succeeded:
        # audio can be re-transcribed by a better engine later, a transcript
        # cannot be un-lost.
        "d ${phoneLaneRoot}/phone/speech 0755 ${userName} users -"
        # What prime holds for the phone, moved here from the retired
        # phone-drain module: what the app FETCHES (glance and steering are
        # generated on request; receipts, notifications and decks are files)
        # and the executed-intent tokens that make a re-delivered intent a
        # no-op. On the NVMe volume rather than the wear-limited root, and
        # under /realm/state because losing the token set would let an
        # already-executed intent run a second time after a reboot.
        "d /realm/state/sinnix-phone 0755 ${userName} users -"
        "d /realm/state/sinnix-phone/inbox 0755 ${userName} users -"
        "d /realm/state/sinnix-phone/inbox/receipts 0755 ${userName} users -"
        "d /realm/state/sinnix-phone/inbox/notify 0755 ${userName} users -"
        "d /realm/state/sinnix-phone/inbox/decks 0755 ${userName} users -"
        "d /realm/state/sinnix-phone/tokens 0755 ${userName} users -"
      ];

      environment.systemPackages = [
        scriptPkgs.sinnix-phone-dispatcher
      ];

      sinnix.runtime.surfaces = {
        phone-dispatcher = {
          unit = "sinnix-phone-dispatcher.service";
          manager = "user";
          resourceClass = "interactive-agent";
          observe = {
            enable = true;
            restartable = true;
          };
          # The ambient archive lands HERE now, not through the drain: the
          # capture app uploads each finished chunk to this service and
          # deletes its copy only once the hash comes back verified. The lane
          # is declared beside the unit that receives it so the thing that
          # can fail is the thing being watched -- it sat on phone-drain
          # until 2026-08-17, which by then was a unit that no longer touched
          # these files. The drain itself is gone now; what the phone cannot
          # push (its system log, which needs READ_LOGS) is pulled by
          # sinnix-phone-logcat, and nothing else is.
          #
          # Two hours, where the pull-era budget was a day. A chunk closes
          # every five minutes and ships within a heartbeat, so the only
          # honest reasons for silence are a phone off wifi or genuinely not
          # recording -- and both of those are worth hearing about long
          # before tomorrow.
          #
          # phone-speech and the app's event lane moved here from the retired
          # sinnix-phone-receiver surface (sinnix-tjqi): the dispatcher's
          # embedded TCP receiver is what writes them now, so the lane
          # declaration sits beside the unit that can actually fail to write
          # it, same reasoning as phone-ambient above. Fields unchanged.
          captures = [
            {
              name = "phone-ambient";
              path = "/realm/data/machine/phone/ambient";
              cadenceSeconds = 300;
              staleAfterSeconds = 7200;
            }
            {
              # eventDriven with no staleness budget: the phone pushes when
              # it has something to say, so silence measures the operator's
              # day rather than this service.
              name = "phone-speech";
              path = "${phoneLaneRoot}/phone-speech";
              eventDriven = true;
            }
            {
              # The app's own event log -- battery, health, location,
              # thermal, notifications, instrument runs, and the lane_blocked
              # records that say when one of those stopped and why. The
              # richest lane the phone has, and the one `sinnix-phone
              # app-status` answers from when adb is down, which is when the
              # question matters most.
              #
              # It arrives here as byte ranges appended to the day file
              # (/phone/v1/events), which is why the budget is half an hour
              # rather than the drain's day: batches leave the phone on a 20
              # second heartbeat, so the budget only has to absorb an
              # ordinary phone-off-the-tailnet stretch.
              #
              # This replaced a second lane, `phone-event`, which
              # carried a live TCP MIRROR of the same records into a
              # different directory. Two lanes for one subject meant every
              # consumer had to dedup them, and the mirror could never be the
              # authority anyway: its cursor started at end-of-file, so
              # anything written while it was off did not exist as far as it
              # was concerned. That directory keeps its files as history;
              # nothing writes it any more, so it is no longer declared.
              name = "phone-events";
              path = "/realm/data/machine/phone/events";
              cadenceSeconds = 20;
              staleAfterSeconds = 1800;
            }
          ];
        };
      };

      home-manager.users.${userName} = {
        home.packages = [
          scriptPkgs.sinnix-elicit
        ];

        systemd.user.services.sinnix-hub = {
          Unit = {
            Description = "Sinnix tailnet hub (Caddy)";
            After = [ "sinnix-ops-reducer.socket" ];
            # The reducer renders every page Caddy does not serve off disk and
            # takes the annotation posts, so its socket has to exist before the
            # proxy takes a request.
            Wants = [ "sinnix-ops-reducer.socket" ];
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

        systemd.user.services.sinnix-phone-dispatcher = {
          Unit.Description = "Prime's live half of the phone's dual transport, plus the always-on telemetry receiver";
          Service = {
            Type = "simple";
            # sinnix-steer/sinnix-score are shelled out to (steering rituals,
            # scoring on trace/voice_note arrival, sinnix-tjqi) via the
            # package's own wrapped PATH now (pkgs/sinnix-phone-dispatcher's
            # pkg.nix makeWrapperArgs), not this Environment -- packaging the
            # dispatcher (sinnix-svvz) traded the scripts/ registry's
            # writeShellApplication runtimeInputs wrapper for that mechanism.
            # Kept as the baseline PATH anything else this process shells out
            # to inherits.
            Environment = [ "PATH=/run/wrappers/bin:/run/current-system/sw/bin" ];
            # Resolves the tailnet bind address for the embedded telemetry
            # receiver (SINNIX_PHONE_STREAM_HOST), same pattern as the hub's
            # own resolveBind above and the earlier standalone receiver
            # unit it replaces. Optional-EnvironmentFile for the same reason:
            # systemd loads it before ExecStartPre runs, so it must not be
            # required on a cold start.
            ExecStartPre = "${resolveBindPhoneStream} %t/sinnix/phone-dispatcher-bind.env";
            EnvironmentFile = "-%t/sinnix/phone-dispatcher-bind.env";
            ExecStart = lib.concatStringsSep " " [
              "${scriptPkgs.sinnix-phone-dispatcher}/bin/sinnix-phone-dispatcher"
              "serve"
              "--socket %t/sinnix/phone-dispatcher.sock"
              "--phone-stream-port ${toString phoneStreamPort}"
              "--capture-root ${phoneLaneRoot}"
            ];
            Restart = "on-failure";
            RestartSec = "5s";
            # sd_notify from the serve loop's own thread (server.py), same
            # qokz/ops-reducer pattern: a wedged HTTP server or a hung
            # phone-stream receiver is restarted rather than sitting there
            # answering nothing. Type stays simple rather than notify --
            # READY does not gate start ordering here any more than it does
            # for the reducer, and the value wanted is the crash detection
            # WatchdogSec buys, not a start-order dependency on it.
            NotifyAccess = "main";
            WatchdogSec = "60s";
            NoNewPrivileges = true;
            UMask = "0077";
          };
          Install.WantedBy = [ "default.target" ];
        };

      };
    };
} args
