# claude-quota usage parsing fixture.
_: {
  perSystem =
    { pkgs, ... }:
    {
      checks = {
        claude-quota = pkgs.runCommand "claude-quota-check" { nativeBuildInputs = [ pkgs.python3 ]; } ''
          mkdir -p scripts
          cp ${../../scripts/claude-quota} scripts/claude-quota
          python3 ${./test_claude_quota.py}
          touch "$out"
        '';
      };
    };
}
