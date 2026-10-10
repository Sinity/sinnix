{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      sources = import ../data/agent-cli-sources.nix { inherit pkgs; };
      claude = sources."@anthropic-ai/claude-code";
      codex = sources."@openai/codex";
      gemini = sources."@google/gemini-cli";
      clodex = sources."@bman654/clodex";
      nativeInputs = pkgs.writeText "agent-recovery-inputs.json" (
        builtins.toJSON {
          helper = toString ../../scripts/sinnix-agent-npm-bootstrap;
          sources = builtins.mapAttrs (_: source: toString source) sources;
        }
      );
    in
    {
      checks.agent-dependency-recovery =
        pkgs.runCommand "agent-dependency-recovery-check"
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
            python3 ${./dependency-recovery.py} ${claude.original} ${claude} ${codex.original} ${codex} ${gemini.original} ${gemini} ${clodex.original} ${clodex} ${../../scripts/sinnix-agent-npm-bootstrap}
            mkdir "$out"
            cp ${nativeInputs} "$out/native-inputs.json"
          '';
    };
}
