# Lane-manifest validation fixture: the real scripts/sinnix-validate-lane-manifest
# must accept a disjoint three-lane manifest and reject one whose lanes own
# overlapping paths (a shared hotspot is what makes parallel lanes collide).
#
# Provably fails when: the validator stops rejecting overlapping `owns` paths,
# or stops accepting a valid manifest (verified by relaxing the overlap check
# in the script).
#
# The former git merge sequence here was deleted: it created three branches
# and merged them, which exercises git rather than anything in this repo, and
# no change to sinnix could make it fail.
{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      validator = pkgs.writeShellScriptBin "sinnix-validate-lane-manifest-fixture" (
        builtins.readFile ../../scripts/sinnix-validate-lane-manifest
      );
      agents = pkgs.runCommand "swarm-fixture-agents" { } ''
        mkdir -p $out
        printf '%s\n' '---' 'name: triage' 'description: fixture' '---' > $out/triage.md
        printf '%s\n' '---' 'name: lane' 'description: fixture' '---' > $out/lane.md
        printf '%s\n' '---' 'name: review' 'description: fixture' '---' > $out/review.md
      '';
      fixture =
        pkgs.runCommand "swarm-three-lane-fixture"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.jq
              pkgs.ripgrep
              validator
            ];
          }
          ''
            export HOME=$TMPDIR/home
            mkdir -p "$HOME"
            cat > "$TMPDIR/valid.json" <<'EOF'
            {"lanes":[
              {"id":"a","agent":"lane","model":"gpt-5.6-terra","effort":"high","owns":["a"],"avoids":["b","c"],"verification":["test"],"merge_order":1},
              {"id":"b","agent":"lane","model":"gpt-5.6-terra","effort":"high","owns":["b"],"avoids":["a","c"],"verification":["test"],"merge_order":2},
              {"id":"c","agent":"review","model":"gpt-5.6-terra","effort":"high","owns":["c"],"avoids":["a","b"],"verification":["test"],"merge_order":3}
            ]}
            EOF
            sinnix-validate-lane-manifest-fixture --manifest "$TMPDIR/valid.json" --agents-root ${agents}
            cat > "$TMPDIR/overlap.json" <<'EOF'
            {"lanes":[
              {"id":"a","agent":"lane","model":"m","effort":"high","owns":["shared"],"avoids":[],"verification":["test"],"merge_order":1},
              {"id":"b","agent":"lane","model":"m","effort":"high","owns":["shared/file"],"avoids":[],"verification":["test"],"merge_order":2},
              {"id":"c","agent":"review","model":"m","effort":"high","owns":["other"],"avoids":[],"verification":["test"],"merge_order":3}
            ]}
            EOF
            set +e
            sinnix-validate-lane-manifest-fixture --manifest "$TMPDIR/overlap.json" --agents-root ${agents}
            overlap_status=$?
            set -e
            test "$overlap_status" -ne 0
            touch "$out"
          '';
    in
    {
      checks.swarm-three-lane-fixture = fixture;
    };
}
