{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      hooksJson = import ../../modules/features/dev/agents/hooks.nix {
        inherit pkgs;
        dotsRoot = inputs.self + "/dots";
      };
    in
    {
      checks.agent-hook-parity =
        pkgs.runCommand "agent-hook-parity-check"
          {
            inherit hooksJson;
            nativeBuildInputs = [ pkgs.jq ];
          }
          ''
            jq -e '
              .hooks
              | has("SessionStart") and has("UserPromptSubmit") and has("PreCompact")
              and has("PreToolUse") and has("PostToolUse") and has("Stop")
              and ([.SessionStart[].hooks[].command] | any(contains("bd-prime-if-present")))
              and ([.PreCompact[].hooks[].command] | any(contains("sinnix-context-handoff")))
              and ([.PreToolUse[].hooks[].command] | any(startswith("polylogue-hook PreToolUse")))
              and ([.PostToolUse[].hooks[].command] | any(startswith("polylogue-hook PostToolUse")))
              and ([.Stop[].hooks[].command] | any(startswith("polylogue-hook Stop")))
            ' "$hooksJson" >/dev/null
            touch "$out"
          '';
    };
}
