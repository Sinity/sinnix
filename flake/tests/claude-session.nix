{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
    in
    {
      checks.claude-session =
        pkgs.runCommand "claude-session-check"
          {
            nativeBuildInputs = [ pkgs.python3 ];
            SESSION_HELPER = builtins.path {
              path = ../../dots/_ai/skills/claude-sessions/scripts/sinnix-claude-session;
              name = "sinnix-claude-session";
            };
          }
          ''
            python3 ${./claude_session.py}
            touch "$out"
          '';
    };
}
