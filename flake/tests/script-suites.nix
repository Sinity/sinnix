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
          nativeBuildInputs ? [ ],
        }:
        pkgs.runCommand "sinnix-${name}-suite-check"
          {
            nativeBuildInputs = [
              (pkgs.python3.withPackages (ps: [ ps.pytest ]))
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
      };
    };
}
