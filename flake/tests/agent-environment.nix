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
              pkgs.python3
            ];
          }
          ''
            python3 ${../../scripts/tests/test_agent_environment_publication.py} ${script}
            ${pkgs.bash}/bin/bash ${script} --data ${data} --skills-root ${skills} --agents-root ${agents} --output "$TMPDIR/document.md"
            cp "$TMPDIR/document.md" "$out"
            grep -F 'Fixture skill description' $out
            grep -F '`fixture-agent`' $out
            grep -F 'https://mcp.context7.com/mcp' $out
            test "$(grep -c '^| `fixture-skill`' $out)" = 1
            test "$(grep -c '^### full' $out)" = 1
            if grep -Eq '/(home|persist|realm/cache|realm/data|nix/store)/' $out; then exit 1; fi
          '';
      nativeBootstrapContract =
        pkgs.runCommand "agent-native-bootstrap-contract"
          {
            nativeBuildInputs = [
              pkgs.bash
              pkgs.coreutils
              pkgs.gawk
              pkgs.python3
              pkgs.util-linux
              pkgs.nodejs_22
              pkgs.gnutar
              pkgs.gzip
            ];
          }
          ''
            AGENT_BOOTSTRAP_PATH=${../../scripts/sinnix-agent-npm-bootstrap} \
              python3 ${../../scripts/tests/test_agent_bootstrap.py}
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
      checks.agent-native-bootstrap-contract = nativeBootstrapContract;
    };
}
