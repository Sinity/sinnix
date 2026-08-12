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
    };
}
