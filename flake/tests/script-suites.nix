# Pytest suites that live next to a packaged script rather than inside a
# Python package, and so have no derivation checkPhase to run them. Without
# these checks they were never executed by any tier: verified by mutating
# scripts/sinnix-sqlite-backup's WAL-absent branch, which no check noticed.
#
# The suites exercise the real scripts through subprocess, so each check
# supplies the script's runtimeInputs rather than importing anything.
{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      sinnix-lib = pkgs.callPackage ../../pkgs/sinnix-lib/pkg.nix { };
      sinnix-rank-core = pkgs.callPackage ../../pkgs/sinnix-rank-core/pkg.nix {
        inherit sinnix-lib;
      };
      # The suites resolve their subject as parents[3]/scripts/<name>, so the
      # fixture must reproduce that layout rather than pass a path.
      mkScriptSuite =
        {
          name,
          suiteDir,
          scripts,
          # Where the suite sits in the reproduced tree. A skill's tests
          # resolve the repository root by walking up from their own file, so
          # they only find the scripts they drive under their real path.
          # Sibling sources the suite imports directly (a collector module
          # inlined into a unit, for instance) must sit where the suite
          # expects them, next to its tests directory.
          packageFiles ? [ ],
          pythonPackages ? [ ],
          # Repository files the suite reads at a path of its own choosing --
          # a declarative source it asserts stays untouched, for instance.
          extraFiles ? [ ],
          # Python packages built in this repository rather than named in
          # nixpkgs.
          extraPythonPackages ? [ ],
          nativeBuildInputs ? [ ],
        }:
        pkgs.runCommand "sinnix-${name}-suite-check"
          {
            nativeBuildInputs = [
              (pkgs.python3.withPackages (
                ps: [ ps.pytest ] ++ map (name: ps.${name}) pythonPackages ++ extraPythonPackages
              ))
              pkgs.coreutils
            ]
            ++ nativeBuildInputs;
          }
          ''
            root="$TMPDIR/root"
            mkdir -p "$root/scripts" "$root/pkgs/${name}/tests"
            ${builtins.concatStringsSep "\n" (
              map (script: ''
                install -m 0755 ${../../scripts + "/${script}"} "$root/scripts/${script}"
                patchShebangs "$root/scripts/${script}"
              '') scripts
            )}
            ${builtins.concatStringsSep "\n" (
              map (file: ''
                mkdir -p "$root/pkgs/${name}/$(dirname ${file})"
                cp ${../../pkgs + "/${name}/${file}"} "$root/pkgs/${name}/${file}"
              '') packageFiles
            )}
            ${builtins.concatStringsSep "\n" (
              map (entry: ''
                mkdir -p "$root/$(dirname ${entry.dest})"
                cp ${entry.source} "$root/${entry.dest}"
              '') extraFiles
            )}
            cp ${suiteDir}/*.py "$root/pkgs/${name}/tests/"
            cd "$root"
            HOME="$TMPDIR/home" python3 -m pytest -q "pkgs/${name}/tests"
            touch "$out"
          '';
    in
    {
      checks = {
        device-remote-command-suite = mkScriptSuite {
          name = "sinnix-device-control";
          suiteDir = ../../pkgs/sinnix-device-control/tests;
          scripts = [
            "sinnix-phone"
            "sinnix-quest"
            "sinnix-remote-command"
          ];
          nativeBuildInputs = [
            pkgs.bash
            pkgs.dash
            pkgs.findutils
            pkgs.gawk
            pkgs.ffmpeg
            pkgs.jq
          ];
        };
        url-ledger-suite = mkScriptSuite {
          name = "url-ledger";
          suiteDir = ../../scripts/tests/url-ledger;
          scripts = [ "sinnix-url-ledger" ];
          extraPythonPackages = [ sinnix-lib ];
          nativeBuildInputs = [ pkgs.duckdb ];
        };
        audio-mic-suite = mkScriptSuite {
          name = "audio-mic";
          suiteDir = ../../scripts/tests/audio-mic;
          scripts = [ "audio" ];
          nativeBuildInputs = [ pkgs.jq ];
        };
        # Provably fails when: the stack walk stops descending, drops a merge
        # bound or a reused branch lifetime, loses a second page, passes a
        # head it could not read, or rewrites an unchanged status. Verified by
        # removing the merge-time bound, which fails the bound test.
        stacked-review-threads-status-suite = mkScriptSuite {
          name = "stacked-review-threads-status";
          suiteDir = ../../scripts/tests/stacked-review-threads-status;
          scripts = [ "stacked-review-threads-status" ];
        };
        # Provably fails when: the stall re-trigger fires before its
        # threshold, on a draft, waived or already-reviewed head, twice for one
        # head (marker on a later comments page included), never for a new
        # head, in a dry run, or after a failed comment read on any PR; while
        # a code-review usage-limit notice on any open PR is recent; more than
        # once as the recovery probe, or never after the probe; at all while
        # `codex-review` is not a required context, or after the protection
        # read fails; or when a second page of open PRs or comments goes
        # unread. Verified by deleting the marker check (fails the later-page
        # marker test) and the age check (fails the below-threshold test).
        codex-review-status-suite = mkScriptSuite {
          name = "codex-review-status";
          suiteDir = ../../scripts/tests/codex-review-status;
          scripts = [ "codex-review-status" ];
        };
        # The SQLite backup remains a standalone script package. Its regression
        # suite drives the source script through subprocess, while the
        # machine-telemetry package owns collector tests in its checkPhase.
        sqlite-backup-regression-suite = mkScriptSuite {
          name = "machine-telemetry";
          suiteDir = ../../pkgs/machine-telemetry/tests;
          scripts = [ "sinnix-sqlite-backup" ];
          packageFiles = [ "machine_telemetry/collector.py" ];
          extraPythonPackages = [ sinnix-lib ];
          nativeBuildInputs = [ pkgs.zstd ];
        };
        # Provably fails when: either runner stamps a grammar other than the
        # estate's %Y-%m-%dT%H:%M:%SZ -- the offset-suffix spelling both
        # carried before, for instance. Verified by restoring
        # machine-experiment-run's local
        # `dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()`, which
        # fails the manifest assertion on `2026-09-05T23:39:12+00:00`.
        experiment-manifest-suite = mkScriptSuite {
          name = "machine-experiment-run";
          suiteDir = ../../pkgs/machine-experiment-run/tests;
          scripts = [
            "machine-experiment-run"
            "syslog-index"
          ];
          extraPythonPackages = [ sinnix-lib ];
          nativeBuildInputs = [ pkgs.systemd ];
        };
        # Provably fails when: the drift reporter stops distinguishing the
        # booted configuration revision from the current one, or stops
        # reporting a drift class its manifest describes.
        config-drift-suite = mkScriptSuite {
          name = "sinnix-config-drift";
          suiteDir = ../../pkgs/sinnix-config-drift/tests;
          scripts = [ "sinnix-config-drift" ];
          extraPythonPackages = [ sinnix-lib ];
          nativeBuildInputs = [ pkgs.systemd ];
        };
        # Provably fails when: the atuin word-boundary match regresses to a
        # naive substring LIKE (false positives) or drops the trailing-token
        # position again (false negatives), or the @-edge reachability loop
        # stops iterating to a fixed point and so misses a two-hop dependency.
        census-suite = mkScriptSuite {
          name = "sinnix-census";
          suiteDir = ../../pkgs/sinnix-census/tests;
          scripts = [ "sinnix-census" ];
          extraPythonPackages = [ sinnix-lib ];
        };
        # Provably fails when: either direction of the /realm taxonomy
        # assertion is dropped, or a retired level-1 name is readmitted to the
        # manifest. Verified by all three mutations.
        lake-lint-suite = mkScriptSuite {
          name = "lake-lint";
          suiteDir = ../../pkgs/lake-lint/tests;
          scripts = [ "lake-lint" ];
          extraPythonPackages = [ sinnix-lib ];
        };
        stt-lake-suite = mkScriptSuite {
          name = "sinnix-stt";
          suiteDir = ../../pkgs/sinnix-stt/tests;
          scripts = [ "sinnix-stt" ];
          extraPythonPackages = [ sinnix-lib ];
        };
        stt-review-suite = mkScriptSuite {
          name = "sinnix-stt-review";
          suiteDir = ../../pkgs/sinnix-stt-review/tests;
          scripts = [ "sinnix-stt-review" ];
          pythonPackages = [ "tzdata" ];
          extraPythonPackages = [ sinnix-lib ];
        };
        speaker-verify-suite = mkScriptSuite {
          name = "sinnix-speaker-verify";
          suiteDir = ../../pkgs/sinnix-speaker-verify/tests;
          scripts = [ "sinnix-speaker-verify" ];
          pythonPackages = [ "numpy" ];
          extraPythonPackages = [ sinnix-lib ];
        };
        reading-stack-suite = mkScriptSuite {
          name = "sinnix-reading-stack";
          suiteDir = ../../pkgs/sinnix-reading-stack/tests;
          scripts = [
            "sinnix-reading-stack"
            "sinnix-nav-capture-daemon"
          ];
          # The stack's state file is published through sinnix_lib.atomic_json;
          # the suite drives the real publish rather than a stub, so a change
          # to the atomic write reaches these assertions.
          extraPythonPackages = [ (pkgs.callPackage ../../pkgs/sinnix-lib/pkg.nix { }) ];
        };
        picker-suite = mkScriptSuite {
          name = "sinnix-picker";
          suiteDir = ../../pkgs/sinnix-picker/tests;
          scripts = [ "sinnix-picker" ];
          extraPythonPackages = [ sinnix-lib ];
        };
        ytdlp-suite = mkScriptSuite {
          name = "sinnix-ytdlp";
          suiteDir = ../../pkgs/sinnix-ytdlp/tests;
          scripts = [
            "sinnix-ytdlp"
            "sinnix-video-resolve"
            "sinnix-url-ledger"
          ];
          extraPythonPackages = [ sinnix-lib ];
          nativeBuildInputs = [
            pkgs.bash
            pkgs.duckdb
          ];
        };
        borg-drill-suite = mkScriptSuite {
          name = "sinnix-borg-drill";
          suiteDir = ../../pkgs/sinnix-borg-drill/tests;
          scripts = [ "sinnix-borg-drill" ];
          nativeBuildInputs = [ pkgs.bash pkgs.jq pkgs.util-linux ];
        };
        fs-materialization-suite = mkScriptSuite {
          name = "sinnix-fs";
          suiteDir = ../../pkgs/sinnix-fs/tests;
          scripts = [ "sinnix-fs" ];
          extraPythonPackages = [ sinnix-lib ];
          nativeBuildInputs = [
            pkgs.duckdb
            pkgs.file
          ];
        };
        quest-player-suite = mkScriptSuite {
          name = "sinnix-quest-player";
          suiteDir = ../../pkgs/sinnix-quest-player/tests;
          scripts = [ "sinnix-quest-player" ];
          extraPythonPackages = [ sinnix-lib ];
        };
        # Provably fails when: a binding's ranking identity starts tracking
        # source order or its /nix/store action path, a usage prior stops
        # distinguishing "never measured" from "measured zero", operator
        # comparisons stop displacing that prior at the documented evidence
        # threshold, a retired binding survives into the next manifest, or
        # deck-forge stops taking its drill order from the manifest.
        rank-keybinds-suite = mkScriptSuite {
          name = "sinnix-rank-keybinds";
          suiteDir = ../../pkgs/sinnix-rank-keybinds/tests;
          scripts = [
            "sinnix-rank-keybinds"
            "sinnix-rank"
            "sinnix-deck-forge"
          ];
          extraPythonPackages = [
            sinnix-rank-core
            sinnix-lib
          ];
          extraFiles = [
            {
              source = ../../modules/features/desktop/hyprland/bindings.nix;
              dest = "modules/features/desktop/hyprland/bindings.nix";
            }
          ];
        };
        # Provably fails when: elicit's fit stops reproducing the model its
        # live domains were ranked under (ties, choice sets, item priors, ids
        # the roster no longer carries), `ingest` stops recognising a
        # tombstoned record as one it has already seen and re-imports every
        # undone judgment on every drain, the state migration stops verifying
        # digests, stops moving by rename, or stops refusing to run while the
        # drain could write, or `serve` records a judgment the log already
        # carries, undoes one by rewriting rather than tombstoning, re-asks a
        # pair the operator has already judged, serves a file the roster does
        # not name, or reports a ranking and stopping statistic that are not
        # the engine's own.
        elicit-suite = mkScriptSuite {
          name = "sinnix-elicit";
          suiteDir = ../../pkgs/sinnix-elicit/tests;
          scripts = [
            "sinnix-elicit"
            "sinnix-elicit-migrate"
          ];
          extraPythonPackages = [ sinnix-rank-core ];
        };
      };
    };
}
