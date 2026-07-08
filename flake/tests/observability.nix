# sinnix-observe offline-report runtime check — synthesizes sinex xtask
# history, Polylogue live-ingest, and `below` cgroup/process TSV fixtures and
# asserts the merged JSON/human report shape.
#
# Split out of the former flake/tests-runtime.nix monolith (sinnix-7bu).
{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      scriptRegistry = import ../scripts.nix { inherit inputs pkgs; };
      sinnixObserve = scriptRegistry.packageSet.sinnix-observe;

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
            mkdir -p \
              "$HOME" \
              "$TMPDIR/sinex/.sinex/state"

            sqlite3 "$TMPDIR/sinex/.sinex/state/xtask-history.db" <<'SQL'
            create table invocations (
              id integer primary key,
              command text not null,
              subcommand text,
              started_at text not null,
              finished_at text,
              duration_secs real,
              status text not null,
              cwd text not null,
              pid integer,
              scope_key text,
              launch_mode text,
              is_background integer,
              process_cpu_usage_avg real,
              process_memory_usage_max_mb real,
              process_count_max integer,
              resource_sample_count integer,
              shared_nix_build_slice_memory_usage_max_mb real,
              shared_background_slice_memory_usage_max_mb real
            );
            insert into invocations values (
              42,
              'check',
              null,
              '2026-05-03T12:00:00Z',
              '2026-05-03T12:00:25Z',
              25.0,
              'success',
              '/realm/project/sinex',
              null,
              'scope-fixture',
              'foreground',
              0,
              180.0,
              512.0,
              12,
              4,
              128.0,
              2048.0
            );
            SQL

            sqlite3 "$TMPDIR/polylogue.db" <<'SQL'
            create table live_ingest_attempt (
              attempt_id text primary key,
              started_at text not null,
              updated_at text not null,
              completed_at text,
              status text not null,
              phase text not null,
              queued_file_count integer not null,
              needed_file_count integer not null,
              succeeded_file_count integer not null,
              failed_file_count integer not null,
              input_bytes integer not null,
              source_payload_read_bytes integer not null,
              cursor_fingerprint_read_bytes integer not null,
              parse_time_s real not null,
              convergence_time_s real not null,
              current_source text,
              current_path text,
              error text,
              rss_current_mb real,
              rss_peak_self_mb real,
              rss_peak_children_mb real,
              cgroup_path text,
              cgroup_memory_current_mb real,
              cgroup_memory_peak_mb real,
              cgroup_memory_swap_current_mb real
            );
            insert into live_ingest_attempt values (
              'attempt-fixture',
              '2026-05-03T12:00:00Z',
              '2026-05-03T12:00:12Z',
              '2026-05-03T12:00:12Z',
              'succeeded',
              'converged',
              3,
              2,
              2,
              0,
              4096,
              2048,
              0,
              1.5,
              0.5,
              'codex',
              '/tmp/session.jsonl',
              null,
              300.0,
              512.0,
              64.0,
              '/user.slice/user-1000.slice/user@1000.service/app.slice/polylogued.service',
              768.0,
              1024.0,
              0.0
            );
            SQL

            cat > "$TMPDIR/below-cgroup.tsv" <<'EOF'
            2026-05-03T12:00:10Z	sinex	/user.slice/user-1000.slice/user@1000.service/build.slice/sinex.scope	120.0	536870912	104857600	7.5	0.0
            2026-05-03T12:00:11Z	polylogued	/user.slice/user-1000.slice/user@1000.service/app.slice/polylogued.service	30.0	268435456	20971520	1.5	0.0
            EOF
            cat > "$TMPDIR/below-process.tsv" <<'EOF'
            2026-05-03T12:00:10Z	1001	cargo	S	/user.slice/user-1000.slice/user@1000.service/build.slice/sinex.scope	104857600	536870912	120.0	cargo check --workspace /realm/project/sinex
            2026-05-03T12:00:11Z	1002	polylogued	S	/user.slice/user-1000.slice/user@1000.service/app.slice/polylogued.service	20971520	268435456	30.0	polylogued run --host 127.0.0.1 --port 8765
            EOF

            SINEX_ROOT="$TMPDIR/sinex" \
            SINNIX_OBSERVE_POLYLOGUE_DB="$TMPDIR/polylogue.db" \
            SINNIX_OBSERVE_BELOW_CGROUP_TSV="$TMPDIR/below-cgroup.tsv" \
            SINNIX_OBSERVE_BELOW_PROCESS_TSV="$TMPDIR/below-process.tsv" \
              ${sinnixObserve}/bin/sinnix-observe \
                --offline --format json --since '1 day ago' --duration '1 day' --limit 5 \
                > "$TMPDIR/report.json"

            jq -e '
              .schema == "sinnix-observe-v1" and
              (.workload_rows | any(.source == "sinex.xtask" and .project == "sinex" and (.gaps | index("sinex.invocation.lacks_cgroup")))) and
              (.workload_rows | any(.source == "polylogue.live_attempt" and .project == "polylogue" and .unit == "polylogued.service" and .metrics.source_payload_read_bytes == 2048)) and
              (.workload_rows | any(.source == "below.process" and .project == "sinex")) and
              (.workload_rows | any(.source == "below.process" and .project == "polylogue")) and
              (.gaps_summary."sinex.invocation.lacks_io_bytes" >= 1)
            ' "$TMPDIR/report.json" >/dev/null

            SINEX_ROOT="$TMPDIR/sinex" \
            SINNIX_OBSERVE_POLYLOGUE_DB="$TMPDIR/polylogue.db" \
            SINNIX_OBSERVE_BELOW_CGROUP_TSV="$TMPDIR/below-cgroup.tsv" \
            SINNIX_OBSERVE_BELOW_PROCESS_TSV="$TMPDIR/below-process.tsv" \
              ${sinnixObserve}/bin/sinnix-observe \
                --offline --format human --since '1 day ago' --duration '1 day' --limit 5 \
                > "$TMPDIR/report.txt"

            grep -q '== workload rows ==' "$TMPDIR/report.txt"
            grep -q 'sinex.invocation.lacks_cgroup' "$TMPDIR/report.txt"
            grep -q 'polylogue live ingest' "$TMPDIR/report.txt"

            touch "$out"
          '';
    in
    {
      heavyChecks = {
        sinnix-observe-runtime = sinnixObserveRuntime;
      };
    };
}
