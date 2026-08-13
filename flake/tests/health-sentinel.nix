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
            ];
          }
          ''
            export PATH="$TMPDIR/bin:$PATH"
            mkdir -p "$TMPDIR/bin" "$TMPDIR/capture" "$TMPDIR/state"
            mkdir -p "$TMPDIR/capture-ed-stale" "$TMPDIR/capture-ed-fresh"
            cat > "$TMPDIR/bin/df" <<'EOF_DF'
            #!/usr/bin/env bash
            printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\n'
            printf '/dev/fixture 100 96 4 96%% /fixture\n'
            EOF_DF
            chmod +x "$TMPDIR/bin/df"
            cat > "$TMPDIR/bin/systemctl" <<'EOF_SYSTEMCTL'
            #!/usr/bin/env bash
            if [ -e "$TMPDIR/down" ]; then
              printf 'inactive\n'
            else
              printf 'active\n'
            fi
            EOF_SYSTEMCTL
            chmod +x "$TMPDIR/bin/systemctl"
            # Simulate the observed fixture.service being down for the whole
            # run so the service_failure assertions below have something to
            # match; nothing else in this fixture flips it back up.
            touch "$TMPDIR/down"
            touch -d @0 "$TMPDIR/capture/old"
            # Event-driven lanes carry no numeric cadence (expectedCadenceSeconds
            # is absent), only an absolute expectedStaleAfterSeconds budget. A
            # write older than that budget must be flagged stale even though
            # there is no cadence to compare against; a write inside the budget
            # must stay healthy.
            touch -d @0 "$TMPDIR/capture-ed-stale/old"
            touch "$TMPDIR/capture-ed-fresh/current"
            # Payload degeneracy: both lanes below write at full cadence and
            # are perfectly fresh, so every staleness check calls them
            # healthy. The `dead` lane's declared fields are null in every
            # record (the screen-frames shape from sinnix-3w9n); the `live`
            # lane populates them. `monitor` is populated in BOTH -- it must
            # stay out of the degenerate lane's evidence, proving the check
            # names the specific dead field rather than condemning the lane
            # wholesale. `note` is null in one live record only, proving a
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
            # Upstream-liveness probes (sinnix-pev0): staleness alone cannot
            # tell "legitimately quiet" apart from "upstream publisher never
            # registered". probe-absent starts with no marker file (exit 1,
            # confirmed absent) and gains one partway through the run (exit
            # 0, recovered) -- proving the absent state is a real transition,
            # not just a value that happens to print once. probe-unknown
            # always exits a code that is neither 0 nor 1 (simulating a
            # probe that itself can't determine the answer -- a bus that's
            # gone, malformed output). probe-timeout's command outlives its
            # 1-second budget so `timeout` kills it (exit 124); a probe that
            # times out MUST still surface as unknown, never as healthy by
            # default -- that silent-success failure mode is the entire bug
            # class this feature exists to close.
            probe_marker="$TMPDIR/probe-marker"
            cat > "$TMPDIR/inventory.json" <<EOF_INVENTORY
            {"captures":[{"name":"fixture","path":"$TMPDIR/capture","expectedCadenceSeconds":60},{"name":"ed-stale","path":"$TMPDIR/capture-ed-stale","expectedCadence":"event-driven","expectedStaleAfterSeconds":60},{"name":"ed-fresh","path":"$TMPDIR/capture-ed-fresh","expectedCadence":"event-driven","expectedStaleAfterSeconds":600},{"name":"payload-dead","path":"$TMPDIR/payload-dead","requiredPayloadFields":["window_class","geometry.width","monitor","note"]},{"name":"payload-live","path":"$TMPDIR/payload-live","requiredPayloadFields":["window_class","geometry.width","monitor","note"]},{"name":"probe-absent","path":"$TMPDIR/capture-ed-fresh","livenessProbe":{"command":"[ -e \"$probe_marker\" ] && exit 0 || exit 1","timeoutSeconds":5}},{"name":"probe-unknown","path":"$TMPDIR/capture-ed-fresh","livenessProbe":{"command":"exit 9","timeoutSeconds":5}},{"name":"probe-timeout","path":"$TMPDIR/capture-ed-fresh","livenessProbe":{"command":"sleep 5","timeoutSeconds":1}}],"mounts":[{"path":"/fixture","warnPct":80,"failPct":95}],"observedServices":[{"kind":"service","manager":"system","unit":"fixture.service"}]}
            EOF_INVENTORY
            "${sentinel}/bin/sinnix-health-sentinel" --inventory "$TMPDIR/inventory.json" --state "$TMPDIR/state/state.json" --output "$TMPDIR/state/events.jsonl" --check
            "${sentinel}/bin/sinnix-health-sentinel" --inventory "$TMPDIR/inventory.json" --state "$TMPDIR/state/state.json" --output "$TMPDIR/state/events.jsonl" --check
            jq -s -e '
              length == 10
              and any(.[]; .type == "capture_stale" and .unit == "fixture" and .status == "stale")
              and any(.[]; .type == "capture_stale" and .unit == "ed-stale" and .status == "stale")
              and any(.[]; .type == "capture_stale" and .unit == "ed-fresh" and .status == "healthy")
              and any(.[]; .type == "mount_capacity" and .status == "failed")
              and any(.[]; .type == "service_failure" and .ok == false)
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
            "${sentinel}/bin/sinnix-health-sentinel" --inventory "$TMPDIR/inventory.json" --state "$TMPDIR/state/state.json" --output "$TMPDIR/state/events.jsonl" --check
            jq -s -e '
              length == 12
              and any(.[]; .type == "capture_stale" and .unit == "fixture" and .status == "healthy")
              and any(.[]; .type == "service_failure" and .ok == false)
              and any(.[]; .type == "publisher_liveness" and .unit == "probe-absent" and .status == "healthy" and .ok)
            ' "$TMPDIR/state/events.jsonl" >/dev/null
            touch "$out"
          '';
    };
}
