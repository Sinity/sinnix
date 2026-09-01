# Contract checks for the daily campaign consumer units and their reports.
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      testLib = import ../test-lib.nix { inherit inputs lib; };
      inherit (testLib) evalTestSpec mkServiceTest;
      serviceSpec = mkServiceTest {
        name = "campaign-consumers-units";
        service = "campaign-consumers";
        extraModules = [
          ({ ... }: {
            sinnix.services.sinnixd.enable = true;
            sinnix.services.campaign-consumers.eventSpool = "/tmp/campaign/events.jsonl";
            sinnix.services.campaign-consumers.outputDir = "/tmp/campaign/output";
          })
        ];
        assertions = config:
          let
            trajectory = config.systemd.user.services.sinnix-campaign-trajectory;
            digest = config.systemd.user.services.sinnix-result-gap-digest;
          in
          [
            {
              assertion = config.systemd.user.timers ? sinnix-campaign-trajectory;
              message = "trajectory consumer must have a scheduled user timer";
            }
            {
              assertion = config.systemd.user.timers ? sinnix-result-gap-digest;
              message = "result-gap consumer must have a scheduled user timer";
            }
            {
              assertion = trajectory.serviceConfig.TimeoutStartSec == "2min"
                && digest.serviceConfig.TimeoutStartSec == "2min";
              message = "consumer units must have bounded runtime";
            }
            {
              assertion = trajectory.onFailure == [ "sinnix-unit-failure-notify@%n.service" ]
                && digest.onFailure == [ "sinnix-unit-failure-notify@%n.service" ];
              message = "consumer failures must use the typed failure event route";
            }
            {
              assertion = lib.hasInfix "sinnix-campaign-trajectory" trajectory.serviceConfig.ExecStart
                && lib.hasInfix "sinnix-result-gap-digest" digest.serviceConfig.ExecStart;
              message = "scheduled units must execute the declared consumer commands";
            }
          ];
      };
      evaluated = evalTestSpec system serviceSpec;
      fixture = pkgs.runCommand "campaign-consumer-fixture" {
        nativeBuildInputs = [ pkgs.coreutils pkgs.python3 ];
      } ''
        root="$TMPDIR/state"
        trajectory="$TMPDIR/sinnix-campaign-trajectory"
        digest="$TMPDIR/sinnix-result-gap-digest"
        cp ${../../scripts/sinnix-campaign-trajectory} "$trajectory"
        cp ${../../scripts/sinnix-result-gap-digest} "$digest"
        chmod +x "$trajectory" "$digest"
        patchShebangs "$trajectory" "$digest"
        mkdir -p "$root/jobs" "$root/jobs-archive" "$root/results" "$root/output"
        printf '%s\n' '{"kind":"attested-agent","job_id":"lane-1","project":"polylogue","phase":"succeeded","completed_at":"2026-08-31T12:00:00+00:00","event_id":"event-1"}' > "$root/events.jsonl"
        printf '%s\n' '{"kind":"attested-agent","job_id":"lane-2","project":"polylogue","phase":"failed","completed_at":"2026-08-31T13:00:00+00:00","event_id":"event-2"}' >> "$root/events.jsonl"
        printf '%s' 'ok' > "$root/results/complete.json"
        printf '%s\n' '{"job_id":"missing","spec":{"result_kind":"json"},"artifacts":{"result":"'$root'/results/missing.json"},"state":{"terminal":true,"phase":"failed"}}' > "$root/jobs/missing.json"
        printf '%s\n' '{"job_id":"empty","spec":{"result_kind":"json"},"artifacts":{"result":"'$root'/results/empty.json"},"state":{"terminal":true,"phase":"succeeded"}}' > "$root/jobs/empty.json"
        : > "$root/results/empty.json"
        printf '%s\n' '{"job_id":"no-artifact","spec":{"result_kind":"exit-status"},"artifacts":{"result":null},"state":{"terminal":true,"phase":"succeeded"}}' > "$root/jobs-archive/no-artifact.json"
        "$trajectory" --event-spool "$root/events.jsonl" --output "$root/output/trajectory.json" --state "$root/output/trajectory.state.json" --date 2026-08-31
        cp "$root/output/trajectory.json" "$root/output/trajectory.first.json"
        "$trajectory" --event-spool "$root/events.jsonl" --output "$root/output/trajectory.json" --state "$root/output/trajectory.state.json" --date 2026-08-31
        cmp "$root/output/trajectory.first.json" "$root/output/trajectory.json"
        test "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["terminal_count"])' "$root/output/trajectory.json")" = 2
        "$digest" --jobs-state-dir "$root" --event-spool "$root/events.jsonl" --output "$root/output/gaps.jsonl" --state "$root/output/gaps.state.json" --date 2026-08-31
        "$digest" --jobs-state-dir "$root" --event-spool "$root/events.jsonl" --output "$root/output/gaps.jsonl" --state "$root/output/gaps.state.json" --date 2026-08-31
        test "$(wc -l < "$root/output/gaps.jsonl")" = 1
        test "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["gap_count"])' "$root/output/gaps.jsonl")" = 2
        ! grep -Fq 'no-artifact' "$root/output/gaps.jsonl"
        touch "$out"
      '';
    in
    {
      checks.campaign-consumers-units = evaluated.config.system.build.toplevel;
      checks.campaign-consumers-fixture = fixture;
    };
}
