# Provider quota normalization, redaction, and disagreement fixture.
_: {
  perSystem =
    { sinnixScriptRegistry, pkgs, ... }:
    {
      checks = {
        claude-quota = pkgs.runCommand "claude-quota-check" { nativeBuildInputs = [ pkgs.python3 ]; } ''
          mkdir -p scripts
          cp ${../../scripts/claude-quota} scripts/claude-quota
          python3 ${./test_claude_quota.py}
          touch "$out"
        '';
        quota = sinnixScriptRegistry.packageSet.sinnix-quota;
        codexbar = sinnixScriptRegistry.packageSet.sinnix-quota.passthru.codexbar;
      };
    };
}
