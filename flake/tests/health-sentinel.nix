# Inventory health transition fixture: stale capture, capacity, failure,
# recovery, and duplicate suppression use the production sentinel script.
{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      scriptRegistry = import ../scripts.nix { inherit inputs pkgs; };
      sentinel = scriptRegistry.packageSet.sinnix-health-sentinel;
      sentinelSource = ../../scripts/sinnix-health-sentinel;
      # The runCommand sandbox has no /usr/bin/env, so a fixture shebang of
      # `#!/usr/bin/env bash` fails to exec with ENOENT. The df/systemctl
      # fixtures below splice the bash store path in directly instead.
      fixtureBash = "${pkgs.bash}/bin/bash";
    in
    {
      checks.health-sentinel =
        pkgs.runCommand "health-sentinel-check"
          {
            nativeBuildInputs = [
              pkgs.coreutils
              pkgs.findutils
              pkgs.jq
              pkgs.gawk
              pkgs.python3
            ];
          }
          ''
            export PATH="$TMPDIR/bin:$PATH"
            # Exercise the packaged binary once, purely to prove packaging
            # (shellcheck, shebang patching, PATH wiring) still succeeds --
            # every functional assertion below runs against the raw script
            # instead. writeShellApplication's wrapper (script-discovery.nix)
            # always prepends its OWN runtimeInputs ahead of the caller's
            # PATH, so the wrapped binary can never see this file's
            # df/systemctl fixtures however PATH is exported beforehand.
            : "${sentinel}"
            mkdir -p "$TMPDIR/bin" "$TMPDIR/capture" "$TMPDIR/state"
            mkdir -p "$TMPDIR/capture-ed-stale" "$TMPDIR/capture-ed-fresh"
            cat > "$TMPDIR/bin/df" <<'EOF_DF'
            #!${fixtureBash}
            printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\n'
            printf '/dev/fixture 100 96 4 96%% /fixture\n'
            EOF_DF
            chmod +x "$TMPDIR/bin/df"
            # The sentinel judges a service's resting state from
            # ActiveState/Type/Result/WantedBy, with no hardcoded unit list.
            # Each fixture below stands in for one resting-state shape:
            #   fixture.service           -- WantedBy set, down: a daemon
            #                                 that should be running, isn't.
            #   oneshot-done.service      -- Type=oneshot, Result=success:
            #                                 ran and exited cleanly.
            #   oneshot-failed.service    -- Type=oneshot, Result=exit-code:
            #                                 ran and failed.
            #   backend-idle.service      -- WantedBy empty: an on-demand
            #                                 backend idled out cleanly
            #                                 (the ai-control.nix shape).
            #   backend-crashed.service   -- WantedBy empty but Result not
            #                                 success: "on-demand" excuses
            #                                 being inactive, not crashing.
            #   socket-proxy-declared.service -- WantedBy still set, but the
            #                                 inventory declares
            #                                 activation.mode=="socket-proxy":
            #                                 that declaration alone suffices.
            #   usersurf.service          -- manager=="user" with no live
            #                                 session bus in the sandbox: an
            #                                 unreachable user manager must
            #                                 report "unknown", never a
            #                                 silent "healthy" or "failed".
            cat > "$TMPDIR/bin/systemctl" <<'EOF_SYSTEMCTL'
            #!${fixtureBash}
            if [ "''${1:-}" = "--user" ]; then shift; fi
            # Recovery verbs the socket sweep issues against a latched socket.
            case "''${1:-}" in
              reset-failed|start) exit 0 ;;
            esac
            shift # drop "show"
            # `show` takes MANY units: the sentinel batches every user-manager
            # unit into one call to keep sudo (and its three PAM journal lines
            # per invocation) off the per-unit path. Collect the unit
            # arguments, drop the -p property flags, and emit one Id=-keyed
            # block per unit separated by a blank line, exactly as systemctl
            # does.
            units=()
            while [ "$#" -gt 0 ]; do
              case "$1" in
                -p) shift 2 ;;
                -*) shift ;;
                *) units+=("$1"); shift ;;
              esac
            done
            first=1
            for unit in "''${units[@]}"; do
              [ "$first" -eq 1 ] || printf '\n'
              first=0
            case "$unit" in
              fixture.service)
                active=inactive; type=simple; result=success; wanted=multi-user.target ;;
              oneshot-done.service)
                active=inactive; type=oneshot; result=success; wanted= ;;
              oneshot-failed.service)
                active=inactive; type=oneshot; result=exit-code; wanted= ;;
              backend-idle.service)
                active=inactive; type=exec; result=success; wanted= ;;
              backend-crashed.service)
                active=inactive; type=exec; result=exit-code; wanted= ;;
              socket-proxy-declared.service)
                active=inactive; type=exec; result=success; wanted=multi-user.target ;;
              usersurf.service)
                exit 1 ;;
              proxy-latched.socket)
                active=failed; type=simple; result=trigger-limit-hit; wanted=sockets.target ;;
              *)
                active=active; type=simple; result=success; wanted=multi-user.target ;;
            esac
            printf 'Id=%s\nActiveState=%s\nType=%s\nResult=%s\nWantedBy=%s\n' "$unit" "$active" "$type" "$result" "$wanted"
            done
            EOF_SYSTEMCTL
            chmod +x "$TMPDIR/bin/systemctl"
            cat > "$TMPDIR/bin/sudo" <<'EOF_SUDO'
            #!${fixtureBash}
            if [ "''${1:-}" = "-u" ]; then shift 2; fi
            while [[ "''${1:-}" == *=* ]]; do
              export "$1"
              shift
            done
            exec "$@"
            EOF_SUDO
            chmod +x "$TMPDIR/bin/sudo"
            mkdir -p "$TMPDIR/user-bus/1000"
            python3 - "$TMPDIR/user-bus/1000/bus" <<'PY_USER_BUS' &
            import socket, sys
            server = socket.socket(socket.AF_UNIX)
            server.bind(sys.argv[1])
            server.listen(1)
            server.accept()
            PY_USER_BUS
            user_bus_pid=$!
            trap 'kill "$user_bus_pid" 2>/dev/null || true' EXIT
            export SINNIX_HEALTH_SENTINEL_USER_BUS_ROOT="$TMPDIR/user-bus"
            touch -d @0 "$TMPDIR/capture/old"
            # Event-driven lanes carry no expectedCadenceSeconds, only an
            # absolute expectedStaleAfterSeconds budget: a write older than
            # the budget must be flagged stale with no cadence to compare
            # against; a write inside it must stay healthy.
            touch -d @0 "$TMPDIR/capture-ed-stale/old"
            touch "$TMPDIR/capture-ed-fresh/current"
            # Payload degeneracy: both lanes write at full cadence and are
            # fresh, so staleness alone calls them healthy. The `dead` lane's
            # declared fields are null in every record; `live` populates
            # them. `monitor` is populated in BOTH -- it must stay out of the
            # degenerate lane's evidence, proving the check names the
            # specific dead field rather than condemning the lane wholesale.
            # `note` is null in one live record only, proving a
            # sometimes-null field never raises an alarm.
            mkdir -p "$TMPDIR/payload-dead" "$TMPDIR/payload-live"
            for seq in 1 2 3 4 5 6; do
              printf '{"schema":"sinnix-capture-v1","seq":%s,"payload":{"window_class":null,"geometry":{},"monitor":"DP-3","note":"x"}}\n' "$seq" >> "$TMPDIR/payload-dead/dead-20260813.jsonl"
              printf '{"schema":"sinnix-capture-v1","seq":%s,"payload":{"window_class":"kitty","geometry":{"width":1920},"monitor":"DP-3","note":null}}\n' "$seq" >> "$TMPDIR/payload-live/live-20260813.jsonl"
            done
            printf '{"schema":"sinnix-capture-v1","seq":7,"payload":{"window_class":"kitty","geometry":{"width":1920},"monitor":"DP-3","note":"present"}}\n' >> "$TMPDIR/payload-live/live-20260813.jsonl"
            # The sidecar index carries no payload at all; the check must skip
            # it rather than read it as a lane full of degenerate records.
            printf '{"ts":1,"seq":1,"file":"live-20260813.jsonl"}\n' >> "$TMPDIR/payload-live/live-index.jsonl"
            # Upstream-liveness probes: staleness alone cannot tell
            # "legitimately quiet" apart from "publisher never registered".
            # probe-absent starts with no marker file (exit 1) and gains one
            # partway through the run (exit 0), so the absent state is proven
            # a real transition rather than a value that prints once.
            # probe-unknown exits neither 0 nor 1 (a probe that itself cannot
            # determine the answer). probe-timeout outlives its 1-second
            # budget so `timeout` kills it (exit 124); a probe that times out
            # MUST surface as unknown, never healthy by default.
            probe_marker="$TMPDIR/probe-marker"
            cat > "$TMPDIR/inventory.json" <<EOF_INVENTORY
            {"captures":[{"name":"fixture","path":"$TMPDIR/capture","expectedCadenceSeconds":60},{"name":"ed-stale","path":"$TMPDIR/capture-ed-stale","expectedCadence":"event-driven","expectedStaleAfterSeconds":60},{"name":"ed-fresh","path":"$TMPDIR/capture-ed-fresh","expectedCadence":"event-driven","expectedStaleAfterSeconds":600},{"name":"payload-dead","path":"$TMPDIR/payload-dead","requiredPayloadFields":["window_class","geometry.width","monitor","note"]},{"name":"payload-live","path":"$TMPDIR/payload-live","requiredPayloadFields":["window_class","geometry.width","monitor","note"]},{"name":"probe-absent","path":"$TMPDIR/capture-ed-fresh","livenessProbe":{"command":"[ -e \"$probe_marker\" ] && exit 0 || exit 1","timeoutSeconds":5}},{"name":"probe-unknown","path":"$TMPDIR/capture-ed-fresh","livenessProbe":{"command":"exit 9","timeoutSeconds":5}},{"name":"probe-timeout","path":"$TMPDIR/capture-ed-fresh","livenessProbe":{"command":"sleep 5","timeoutSeconds":1}},{"name":"unbudgeted-never-wrote","path":"$TMPDIR/does-not-exist"}],"mounts":[{"path":"/fixture","warnPct":80,"failPct":95}],"observedServices":[{"kind":"service","manager":"system","unit":"fixture.service"},{"kind":"service","manager":"system","unit":"oneshot-done.service"},{"kind":"service","manager":"system","unit":"oneshot-failed.service"},{"kind":"service","manager":"system","unit":"backend-idle.service"},{"kind":"service","manager":"system","unit":"backend-crashed.service"},{"kind":"service","manager":"system","unit":"socket-proxy-declared.service","activationMode":"socket-proxy"},{"kind":"service","manager":"user","unit":"usersurf.service"},{"kind":"socket","manager":"system","unit":"proxy-listening.socket"},{"kind":"socket","manager":"system","unit":"proxy-latched.socket"}]}
            EOF_INVENTORY
            bash "${sentinelSource}" --inventory "$TMPDIR/inventory.json" --state "$TMPDIR/state/state.json" --output "$TMPDIR/state/events.jsonl" --check
            bash "${sentinelSource}" --inventory "$TMPDIR/inventory.json" --state "$TMPDIR/state/state.json" --output "$TMPDIR/state/events.jsonl" --check
            jq -s -e '
              length == 24
              and any(.[]; .type == "capture_stale" and .unit == "fixture" and .status == "stale")
              # Lanes declaring neither cadence nor budget used to be filtered
              # out of the staleness sweep entirely, so "declared, wired, never
              # produced a single file" -- the most broken a lane can be --
              # raised nothing. They are all tracked now: one with data reads
              # healthy (no budget to violate), one with none reads stale.
              and any(.[];
                .type == "capture_stale" and .unit == "unbudgeted-never-wrote"
                and .status == "stale" and (.evidence | test("reason=no-file")))
              and any(.[]; .type == "capture_stale" and .unit == "ed-stale" and .status == "stale")
              and any(.[]; .type == "capture_stale" and .unit == "ed-fresh" and .status == "healthy")
              and any(.[]; .type == "mount_capacity" and .status == "failed")
              and any(.[]; .type == "service_failure" and .unit == "fixture.service" and .status == "failed" and .ok == false)
              and any(.[]; .type == "service_failure" and .unit == "oneshot-done.service" and .status == "healthy" and .ok)
              and any(.[]; .type == "service_failure" and .unit == "oneshot-failed.service" and .status == "failed" and .ok == false)
              and any(.[]; .type == "service_failure" and .unit == "backend-idle.service" and .status == "healthy" and .ok)
              and any(.[]; .type == "service_failure" and .unit == "backend-crashed.service" and .status == "failed" and .ok == false)
              and any(.[]; .type == "service_failure" and .unit == "socket-proxy-declared.service" and .status == "healthy" and .ok)
              and any(.[]; .type == "service_failure" and .unit == "usersurf.service" and .status == "unknown" and .ok == false)
              and any(.[]; .type == "socket_failure" and .unit == "proxy-listening.socket" and .status == "healthy" and .ok)
              and any(.[];
                .type == "socket_failure" and .unit == "proxy-latched.socket"
                and .status == "healthy" and .ok
                and (.evidence | test("result=trigger-limit-hit"))
                and (.evidence | test("recovered=reset-failed\\+start")))
              and any(.[];
                .type == "capture_payload" and .unit == "payload-dead"
                and .status == "degenerate" and .ok == false
                and (.evidence | test("always_empty=window_class,geometry.width$")))
              and any(.[]; .type == "capture_payload" and .unit == "payload-live" and .ok)
              and any(.[]; .type == "publisher_liveness" and .unit == "probe-absent" and .status == "publisher-absent" and .ok == false)
              and any(.[]; .type == "publisher_liveness" and .unit == "probe-unknown" and .status == "unknown" and .ok == false)
              and any(.[]; .type == "publisher_liveness" and .unit == "probe-timeout" and .status == "unknown" and .ok == false and (.evidence | test("probe_exit=124")))
            ' "$TMPDIR/state/events.jsonl" >/dev/null
            touch "$TMPDIR/capture/current"
            touch "$probe_marker"
            bash "${sentinelSource}" --inventory "$TMPDIR/inventory.json" --state "$TMPDIR/state/state.json" --output "$TMPDIR/state/events.jsonl" --check
            bash "${sentinelSource}" --inventory "$TMPDIR/inventory.json" --state "$TMPDIR/state/state.json" --output "$TMPDIR/state/events.jsonl" --check
            jq -s -e '
              length == 26
              and any(.[]; .type == "capture_stale" and .unit == "fixture" and .status == "healthy")
              and any(.[]; .type == "service_failure" and .unit == "fixture.service" and .ok == false)
              and any(.[]; .type == "publisher_liveness" and .unit == "probe-absent" and .status == "healthy" and .ok)
            ' "$TMPDIR/state/events.jsonl" >/dev/null
            touch "$out"
          '';
    };
}
