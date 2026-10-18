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
          helper = "${../../scripts/sinnix-agent-npm-bootstrap}";
          sources = builtins.mapAttrs (_: toString) sources;
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
            RECOVERY_INPUTS=${nativeInputs} RECOVERY_BOOTSTRAP=${../../scripts/sinnix-agent-npm-bootstrap} RECOVERY_VERIFIER=${../../scripts/tests/verify_agent_recovery.py} python3 ${../../scripts/tests/test_agent_recovery_verification.py}
            python3 ${./dependency-recovery.py} ${claude.original} ${claude} ${codex.original} ${codex} ${gemini.original} ${gemini} ${clodex.original} ${clodex} ${../../scripts/sinnix-agent-npm-bootstrap}
            mkdir "$out"
            cp ${nativeInputs} "$out/native-inputs.json"
          '';
    };
}
