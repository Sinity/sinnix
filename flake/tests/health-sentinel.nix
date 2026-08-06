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
            cat > "$TMPDIR/bin/df" <<'EOF_DF'
            #!/usr/bin/env bash
            printf 'Filesystem 1024-blocks Used Available Capacity Mounted on\n'
            printf '/dev/fixture 100 90 10 90%% /fixture\n'
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
            touch -d @0 "$TMPDIR/capture/old"
            cat > "$TMPDIR/inventory.json" <<EOF_INVENTORY
            {"captures":[{"name":"fixture","path":"$TMPDIR/capture","expectedCadenceSeconds":60}],"mounts":[{"path":"/fixture","warnPct":80,"failPct":95}],"observedServices":[{"kind":"service","manager":"system","unit":"fixture.service"}]}
            EOF_INVENTORY
            "${sentinel}/bin/sinnix-health-sentinel" --inventory "$TMPDIR/inventory.json" --state "$TMPDIR/state/state.json" --output "$TMPDIR/state/events.jsonl" --check
            "${sentinel}/bin/sinnix-health-sentinel" --inventory "$TMPDIR/inventory.json" --state "$TMPDIR/state/state.json" --output "$TMPDIR/state/events.jsonl" --check
            jq -s -e 'length == 3 and any(.[]; .type == "capture_stale" and .status == "stale") and any(.[]; .type == "mount_capacity" and .status == "failed") and any(.[]; .type == "service_failure" and .ok == false)' "$TMPDIR/state/events.jsonl" >/dev/null
            touch "$TMPDIR/capture/current"
            "${sentinel}/bin/sinnix-health-sentinel" --inventory "$TMPDIR/inventory.json" --state "$TMPDIR/state/state.json" --output "$TMPDIR/state/events.jsonl" --check
            jq -s -e 'length == 4 and any(.[]; .type == "capture_stale" and .status == "healthy") and any(.[]; .type == "service_failure" and .ok == false)' "$TMPDIR/state/events.jsonl" >/dev/null
            touch "$out"
          '';
    };
}
