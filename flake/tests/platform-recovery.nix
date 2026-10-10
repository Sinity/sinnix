{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      sources = import ../data/agent-cli-sources.nix { inherit pkgs; };
      claude = sources."@anthropic-ai/claude-code";
      codex = sources."@openai/codex";
    in
    {
      checks.agent-platform-recovery =
        pkgs.runCommand "agent-platform-recovery-check"
          {
            nativeBuildInputs = [
              pkgs.python3
              pkgs.nodejs_22
              pkgs.bash
              pkgs.coreutils
              pkgs.util-linux
              pkgs.gnutar
              pkgs.gzip
            ];
          }
          ''
            python3 ${./platform-recovery.py} ${claude.original} ${claude} ${codex.original} ${codex} ${../../scripts/sinnix-agent-npm-bootstrap}
            touch "$out"
          '';
    };
}
