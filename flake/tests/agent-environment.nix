# Provably fails when: scripts/sinnix-agent-environment-doc stops rendering a
# skill/agent/server row from its inputs, emits a row twice, or leaks a local
# absolute path (/home, /persist, /nix/store) into the public document.
{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      script = ../../scripts/sinnix-agent-environment-doc;
      data = pkgs.writeText "agent-environment-fixture.json" (
        builtins.toJSON {
          profiles = [
            {
              name = "full";
              client = "codex";
              tiers = [ "remote-core" ];
              servers = [ "context7" ];
            }
          ];
          servers = [
            {
              name = "context7";
              tier = "remote-core";
              transport = "http";
              url = "https://mcp.context7.com/mcp";
              clients = [ "codex" ];
            }
          ];
          skills = [ "fixture-skill" ];
        }
      );
      skills = pkgs.runCommand "agent-environment-fixture-skills" { } ''
        mkdir -p $out
        cat > $out/fixture-skill.md <<'EOF'
        ---
        name: fixture-skill
        description: Fixture skill description
        ---
        Fixture body.
        EOF
      '';
      agents = pkgs.runCommand "agent-environment-fixture-agents" { } ''
        mkdir -p $out
        cat > $out/fixture-agent.md <<'EOF'
        ---
        name: fixture-agent
        description: Fixture agent description
        model: haiku
        effort: medium
        ---
        Fixture body.
        EOF
      '';
      rendered =
        pkgs.runCommand "agent-environment-fixture-rendered"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.findutils
              pkgs.gawk
              pkgs.jq
              pkgs.ripgrep
            ];
          }
          ''
            ${pkgs.bash}/bin/bash ${script} --data ${data} --skills-root ${skills} --agents-root ${agents} --output $out
            grep -F 'Fixture skill description' $out
            grep -F '`fixture-agent`' $out
            grep -F 'https://mcp.context7.com/mcp' $out
            test "$(grep -c '^| `fixture-skill`' $out)" = 1
            test "$(grep -c '^### full' $out)" = 1
            if grep -Eq '/(home|persist|realm/cache|realm/data|nix/store)/' $out; then exit 1; fi
          '';
      nativeRunnerContract =
        pkgs.runCommand "agent-native-runner-contract"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.gawk
            ];
          }
          ''
            mkdir -p "$TMPDIR/bin" "$TMPDIR/worktree"
            cat > "$TMPDIR/bin/codex" <<EOF
            #!${pkgs.bash}/bin/bash
            printf '%s\\n' "\$@" > "\$CODEX_ARGS"
            EOF
            chmod +x "$TMPDIR/bin/codex"
            printf 'fixture prompt' > "$TMPDIR/prompt"
            export CODEX_ARGS="$TMPDIR/codex-args"
            export PATH="$TMPDIR/bin:$PATH"
            ${pkgs.bash}/bin/bash ${../../dots/_ai/skills/agent-runtime/scripts/run_agent_prompt.sh} \
              --agent codex \
              --workdir "$TMPDIR/worktree" \
              --prompt-file "$TMPDIR/prompt" \
              --last-file "$TMPDIR/result" \
              --model fixture-model \
              --reasoning-effort medium
            awk '
              previous == "-c" && $0 == "shell_environment_policy.inherit=all" { found = 1 }
              { previous = $0 }
              END { exit !found }
            ' "$CODEX_ARGS"
            touch "$out"
          '';
    in
    {
      checks.agent-environment-doc =
        pkgs.runCommand "agent-environment-doc-check"
          {
            inherit rendered;
          }
          ''
            test -s $rendered
            touch $out
          '';
      checks.agent-native-runner-contract = nativeRunnerContract;
    };
}
