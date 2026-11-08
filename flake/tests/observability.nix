# Provably fails when: sinnix-observe stops classifying a gap it can see in
# its inputs (verified by renaming the sinex.invocation.lacks_cgroup gap),
# drops a source from the merged report, or changes the report schema without
# the consumers being updated.
#
# sinnix-observe offline-report runtime check — synthesizes sinex xtask
# history (devkit's run store), Polylogue daemon status, and `below` cgroup/process TSV fixtures and
# asserts the merged JSON/human report shape.
{ inputs, ... }:
{
  perSystem =
    {
      system,
      sinnixScriptRegistry,
      ...
    }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      sinnixObserve = sinnixScriptRegistry.packageSet.sinnix-runtime;
      lib = inputs.nixpkgs.lib;
      testLib = import ../test-lib.nix { inherit inputs lib; };
      generationLogCheck =
        name: revision: expected:
        let
          dataDir = "/build/generation-${name}";
          evaluated = testLib.evalTestSpec system (
            testLib.mkServiceTest {
              name = "generation-${name}";
              service = "machine-telemetry";
              extraModules = [
                {
                  system.configurationRevision = revision;
                  sinnix.paths.machineRoot = dataDir;
                }
              ];
              assertions = _: [ ];
            }
          );
          activation = pkgs.writeShellScript "generation-${name}" evaluated.config.system.activationScripts.lynchpinGenerationLog.text;
        in
        pkgs.runCommand "telemetry-generation-${name}" { inherit expected; } ''
          ${activation}
          ${pkgs.jq}/bin/jq -e --arg expected "$expected" '.sinnix_revision == $expected' ${dataDir}/generations.jsonl
          touch "$out"
        '';

      sinnixObserveRuntime =
        pkgs.runCommand "sinnix-observe-runtime-check"
          {
            nativeBuildInputs = [
              pkgs.coreutils
              pkgs.gnugrep
              pkgs.jq
              pkgs.python3
              pkgs.sqlite
            ];
          }
          ''
            export HOME="$TMPDIR/home"
            mkdir -p "$HOME/.local/state/devkit"

            sqlite3 "$HOME/.local/state/devkit/history.db" <<'SQL'
            create table runs (
              id integer primary key,
              project text not null,
              checkout text not null,
              command text not null,
              args text not null,
              pid integer not null,
              agentctl_job text,
              started_ms integer not null,
              duration_ms integer,
              status text not null,
              failure text
            );
            insert into runs values (
              42, 'sinex', '/realm/project/sinex/repo', 'check', '--fixture',
              1001, 'sinex-check-fixture', 1777809600000, 25000, 'passed', null
            );
            insert into runs values (
              43, 'polylogue', '/realm/project/polylogue/repo', 'check', '--fixture',
              1002, null, 1777809600000, 25000, 'passed', null
            );
            SQL

            cat > "$TMPDIR/polylogue" <<'EOF'
            #!/bin/sh
            echo '{"pid":1002,"uptime_seconds":60,"busy":false,"passes":3,"mode":{"state":"standalone"},"last_pass":{"inputs_seen":10,"inputs_changed":2,"bytes_read":4096,"messages_written":5,"seconds":0.5,"errors":[]},"store":{"sessions":7,"messages":70}}'
            EOF
            chmod +x "$TMPDIR/polylogue"

            cat > "$TMPDIR/below-cgroup.tsv" <<'EOF'
            2026-05-03T12:00:10Z	sinex	/user.slice/user-1000.slice/user@1000.service/build.slice/sinex.scope	120.0	536870912	104857600	7.5	0.0
            2026-05-03T12:00:11Z	polylogue	/user.slice/user-1000.slice/user@1000.service/live.slice/polylogue-live.service	30.0	268435456	20971520	1.5	0.0
            EOF
            cat > "$TMPDIR/below-process.tsv" <<'EOF'
            2026-05-03T12:00:10Z	1001	cargo	S	/user.slice/user-1000.slice/user@1000.service/build.slice/sinex.scope	104857600	536870912	120.0	cargo check --workspace /realm/project/sinex/repo
            2026-05-03T12:00:11Z	1002	polylogue	S	/user.slice/user-1000.slice/user@1000.service/live.slice/polylogue-live.service	20971520	268435456	30.0	polylogue daemon
            EOF

            SINNIX_OBSERVE_POLYLOGUE="$TMPDIR/polylogue" \
            SINNIX_OBSERVE_BELOW_CGROUP_TSV="$TMPDIR/below-cgroup.tsv" \
            SINNIX_OBSERVE_BELOW_PROCESS_TSV="$TMPDIR/below-process.tsv" \
              ${sinnixObserve}/bin/sinnix-observe \
                --offline --format json --since '1 day ago' --duration '1 day' --limit 5 \
                > "$TMPDIR/report.json"

            jq -e '
              .schema == "sinnix-observe-v1" and
              (.workload_rows | any(.source == "sinex.xtask" and .project == "sinex" and (.gaps | index("sinex.invocation.lacks_cgroup")))) and
              (.workload_rows | any(.source == "sinex.xtask" and .metrics.agentctl_job == "sinex-check-fixture")) and
              (.workload_rows | any(.source == "polylogue.daemon" and .project == "polylogue" and .unit == "polylogue-live.service" and .metrics.last_pass_messages_written == 5)) and
              (.workload_rows | any(.source == "below.process" and .project == "sinex")) and
              (.workload_rows | any(.source == "below.process" and .project == "polylogue")) and
              (.gaps_summary."sinex.invocation.lacks_io_bytes" >= 1)
            ' "$TMPDIR/report.json" >/dev/null

            SINNIX_OBSERVE_POLYLOGUE="$TMPDIR/polylogue" \
            SINNIX_OBSERVE_BELOW_CGROUP_TSV="$TMPDIR/below-cgroup.tsv" \
            SINNIX_OBSERVE_BELOW_PROCESS_TSV="$TMPDIR/below-process.tsv" \
              ${sinnixObserve}/bin/sinnix-observe \
                --offline --format human --since '1 day ago' --duration '1 day' --limit 5 \
                > "$TMPDIR/report.txt"

            grep -q '== workload rows ==' "$TMPDIR/report.txt"
            grep -q 'sinex.invocation.lacks_cgroup' "$TMPDIR/report.txt"
            grep -q 'polylogue daemon' "$TMPDIR/report.txt"

            touch "$out"
          '';
    in
    {
      checks = {
        sinnix-observe-runtime = sinnixObserveRuntime;
        telemetry-generation-unknown = generationLogCheck "unknown" null "unknown";
        telemetry-generation-known = generationLogCheck "known" "fixture-revision" "fixture-revision";
      };
    };
}
