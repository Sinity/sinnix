{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      audit = pkgs.writeShellScriptBin "sinnix-memory-audit-fixture" (
        builtins.readFile ../../scripts/sinnix-memory-audit
      );
    in
    {
      checks.memory-audit = pkgs.runCommand "sinnix-memory-audit-check" {
        nativeBuildInputs = [ audit pkgs.bash pkgs.coreutils pkgs.findutils pkgs.gawk pkgs.jq ];
      } ''
        fixture="$TMPDIR/fixture"
        mkdir -p "$fixture/in-scope" "$fixture/out-of-scope"
        printf '%s\n' '# 2020-01-01 /realm/missing/path' 'This is obsolete and needs review.' > "$fixture/in-scope/MEMORY.md"
        printf '%s\n' '# 2020-01-01 /realm/missing/ignored' > "$fixture/out-of-scope/MEMORY.md"
        before="$(sha256sum "$fixture/in-scope/MEMORY.md")"
        sinnix-memory-audit-fixture --root "$fixture/in-scope" --output "$TMPDIR/report.jsonl"
        after="$(sha256sum "$fixture/in-scope/MEMORY.md")"
        test "$before" = "$after"
        jq -e 'select(.kind == "stale_date" and .line == 1)' "$TMPDIR/report.jsonl" >/dev/null
        jq -e 'select(.kind == "dead_path" and .line == 1 and .value == "/realm/missing/path")' "$TMPDIR/report.jsonl" >/dev/null
        jq -e 'select(.kind == "review_required" and .line == 2)' "$TMPDIR/report.jsonl" >/dev/null
        ! jq -e 'select(.value == "/realm/missing/ignored")' "$TMPDIR/report.jsonl" >/dev/null
        touch "$out"
      '';
    };
}
