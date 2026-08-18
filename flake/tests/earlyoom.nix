# Behavior check for the sinnix earlyoom patches (overlay/package/earlyoom.nix).
# Runs the patched binary in --dryrun against PSI fixtures, so the check
# exercises the real kill decision path rather than asserting on the patch
# text. Memory/swap state comes from the sandbox's real /proc; -m 99 -s 100
# reads any live state as "below limits", which is exactly the shape of the
# 2026-08-16 bwa-mem2 incident (thresholds crossed, machine healthy).
{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      earlyoomPatched = ((import ../overlay/package/earlyoom.nix) { } pkgs pkgs).earlyoom;
    in
    {
      checks = {
        # Provably fails when: the PSI gate stops suppressing kills below
        # --mem-psi-min, stops admitting them at/above it, loses its
        # fail-open behavior on missing pressure data, or the gate flag
        # disappears from the patched binary. Observed red during
        # development: assertion 2 failed loudly while its grep pattern
        # still matched the startup banner, on the same calm-fixture run
        # that assertion 1 had already validated.
        earlyoom-psi-gate =
          pkgs.runCommand "earlyoom-psi-gate-check"
            {
              nativeBuildInputs = [ earlyoomPatched ];
            }
            ''
              set -u
              printf 'some avg10=1.50 avg60=0.80 avg300=0.40 total=1000000\nfull avg10=3.00 avg60=1.20 avg300=0.60 total=500000\n' > calm
              printf 'some avg10=45.00 avg60=30.00 avg300=12.00 total=9000000\nfull avg10=25.00 avg60=18.00 avg300=8.00 total=7000000\n' > stalled

              run() {
                local psi="$1"; shift
                EARLYOOM_PSI_PATH="$psi" timeout 2 earlyoom -m 99 -s 100 --dryrun "$@" 2>&1 || true
              }

              log="$(run "$PWD/calm" --mem-psi-min 20)"
              grep -q 'not killing' <<< "$log" || { echo "FAIL: calm PSI did not suppress the kill"; echo "$log"; exit 1; }
              grep -qE 'sending SIG(TERM|KILL) to process' <<< "$log" && { echo "FAIL: kill fired despite calm PSI"; echo "$log"; exit 1; }

              log="$(run "$PWD/stalled" --mem-psi-min 20)"
              grep -q 'low memory!' <<< "$log" || { echo "FAIL: stalled PSI did not admit the kill"; echo "$log"; exit 1; }

              log="$(run "$PWD/does-not-exist" --mem-psi-min 20)"
              grep -q 'pressure data unavailable' <<< "$log" || { echo "FAIL: missing PSI file not reported"; echo "$log"; exit 1; }
              grep -q 'low memory!' <<< "$log" || { echo "FAIL: gate did not fail open without PSI data"; echo "$log"; exit 1; }

              log="$(run "$PWD/calm")"
              grep -q 'low memory!' <<< "$log" || { echo "FAIL: ungated behavior changed"; echo "$log"; exit 1; }

              touch "$out"
            '';
      };
    };
}
