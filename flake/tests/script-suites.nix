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
      # The suites resolve their subject as parents[3]/scripts/<name>, so the
      # fixture must reproduce that layout rather than pass a path.
      mkScriptSuite =
        {
          name,
          suiteDir,
          scripts,
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
        # Provably fails when: the backup stops handling a WAL-less (parked)
        # database, stops verifying integrity, or leaves its raw intermediate
        # behind. Verified by restoring the old try/except-FileNotFoundError
        # shape around the WAL copy, which cp never raises.
        machine-telemetry-suite = mkScriptSuite {
          name = "machine-telemetry";
          suiteDir = ../../pkgs/machine-telemetry/tests;
          scripts = [ "sinnix-sqlite-backup" ];
          packageFiles = [ "collector.py" ];
          nativeBuildInputs = [ pkgs.zstd ];
        };
        # Provably fails when: the drift reporter stops distinguishing the
        # booted configuration revision from the current one, or stops
        # reporting a drift class its manifest describes.
        config-drift-suite = mkScriptSuite {
          name = "sinnix-config-drift";
          suiteDir = ../../pkgs/sinnix-config-drift/tests;
          scripts = [ "sinnix-config-drift" ];
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
        };
        speaker-verify-suite = mkScriptSuite {
          name = "sinnix-speaker-verify";
          suiteDir = ../../pkgs/sinnix-speaker-verify/tests;
          scripts = [ "sinnix-speaker-verify" ];
          pythonPackages = [ "numpy" ];
        };
        reading-stack-suite = mkScriptSuite {
          name = "sinnix-reading-stack";
          suiteDir = ../../pkgs/sinnix-reading-stack/tests;
          scripts = [
            "sinnix-reading-stack"
            "sinnix-nav-capture-daemon"
          ];
        };
        picker-suite = mkScriptSuite {
          name = "sinnix-picker";
          suiteDir = ../../pkgs/sinnix-picker/tests;
          scripts = [ "sinnix-picker" ];
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
            (pkgs.callPackage ../../pkgs/sinnix-rank-core/pkg.nix { })
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
        # undone judgment on every drain, or the state migration stops
        # verifying digests, stops moving by rename, or stops refusing to run
        # while the drain could write.
        elicit-suite = mkScriptSuite {
          name = "sinnix-elicit";
          suiteDir = ../../pkgs/sinnix-elicit/tests;
          scripts = [
            "sinnix-elicit"
            "sinnix-elicit-migrate"
          ];
          extraPythonPackages = [
            (pkgs.callPackage ../../pkgs/sinnix-rank-core/pkg.nix { })
          ];
        };
      };
    };
}
