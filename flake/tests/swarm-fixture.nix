{ inputs, ... }:
{
  perSystem = { system, ... }:
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
      fixture = pkgs.runCommand "swarm-three-lane-fixture" {
        nativeBuildInputs = [ pkgs.bash pkgs.coreutils pkgs.git pkgs.jq pkgs.ripgrep validator ];
      } ''
        export HOME=$TMPDIR/home
        mkdir -p "$HOME" "$TMPDIR/work"
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
        cd "$TMPDIR/work"
        git init -q --initial-branch=master
        git config user.email fixture@example.invalid
        git config user.name fixture
        git commit --allow-empty -qm base
        for lane in a b c; do
          git switch -qc "lane-$lane"
          printf '%s\n' "$lane" > "$lane.txt"
          git add "$lane.txt"
          git commit -qm "lane $lane"
          git switch -q master
        done
        git merge --no-ff -qm 'merge lane a' lane-a
        git merge --no-ff -qm 'merge lane b' lane-b
        git merge --no-ff -qm 'merge lane c' lane-c
        test "$(git log --format='%s' -6 | sed -n '1p')" = 'merge lane c'
        test -f a.txt -a -f b.txt -a -f c.txt
        touch "$out"
      '';
    in
    {
      checks.swarm-three-lane-fixture = fixture;
    };
}
