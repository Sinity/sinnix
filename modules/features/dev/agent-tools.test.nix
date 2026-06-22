{
  lib,
  mkFeatureTest,
  expect,
  hmFor,
  inputs,
  ...
}:
mkFeatureTest {
  name = "dev-agent-tools";
  feature = "sinnix.features.dev.agentTools.enable";
  extraModules = [
    (
      { ... }:
      {
        sinnix.features.dev.shell.enable = true;
        sinnix.features.dev.mcp-servers.enable = true;
      }
    )
  ];
  assertions =
    config:
    let
      hm = hmFor config;
      findSelfReferentialLinks =
        dir:
        let
          entries = builtins.readDir dir;
          names = builtins.attrNames entries;
          basename = baseNameOf (toString dir);
          directHits = lib.optional (
            entries ? ${basename} && entries.${basename} == "symlink"
          ) "${toString dir}/${basename}";
          nestedHits = lib.concatLists (
            map (
              name: if entries.${name} == "directory" then findSelfReferentialLinks (dir + "/${name}") else [ ]
            ) names
          );
        in
        directHits ++ nestedHits;
      sharedSkillSelfLinks = findSelfReferentialLinks (inputs.self + "/dots/_ai/skills");
    in
    [
      {
        assertion = sharedSkillSelfLinks == [ ];
        message = "Shared skills tree must not contain self-referential symlinks: ${lib.concatStringsSep ", " sharedSkillSelfLinks}";
      }
      (expect.hmFileExists hm ".local/bin/claude" "Claude wrapper must exist")
      (expect.hmFileExists hm ".local/bin/claude-opus" "Claude Opus wrapper must exist")
      (expect.hmFileExists hm ".local/bin/claude-sonnet" "Claude Sonnet wrapper must exist")
      (expect.hmFileExists hm ".local/bin/claude-lite" "Claude bare/no-MCP wrapper must exist")
      {
        assertion = lib.any (pkg: lib.getName pkg == "sinnix-scope") hm.home.packages;
        message = "sinnix-scope must be in the user profile so wrapper runtime fallbacks are real";
      }
      (expect.hmFileExists hm ".local/bin/deepseek" "DeepSeek wrapper must exist")
      (expect.hmFileExists hm ".local/bin/codex" "Codex wrapper must exist")
      (expect.hmFileExists hm ".local/bin/codex-fast" "Codex fast profile wrapper must exist")
      (expect.hmFileExists hm ".local/bin/codex-deep" "Codex deep profile wrapper must exist")
      (expect.hmFileExists hm ".local/bin/codex-max" "Codex max profile wrapper must exist")
      (expect.hmFileExists hm ".local/bin/codex-spark" "Codex Spark profile wrapper must exist")
      (expect.hmFileExists hm ".local/bin/codex-spark-xhigh"
        "Codex Spark xhigh profile wrapper must exist"
      )
      (expect.hmFileTextNotMatches hm ".local/bin/codex" ".*render-agents.*"
        "Codex wrapper must not render AGENTS on every launch"
      )
      (expect.hmFileTextNotMatches hm ".local/bin/claude" ".*agent-fhs.*"
        "Claude wrapper must not launch through buildFHSEnv/bubblewrap"
      )
      (expect.hmFileTextNotMatches hm ".local/bin/codex" ".*agent-fhs.*"
        "Codex wrapper must not launch through buildFHSEnv/bubblewrap"
      )
      (expect.hmFileTextNotMatches hm ".local/bin/gemini" ".*agent-fhs.*"
        "Gemini wrapper must not launch through buildFHSEnv/bubblewrap"
      )
      (expect.persistedHomeDir config ".config/claude"
        "Claude config directory must be persisted under ~/.config/claude"
      )
      (expect.persistedHomeDir config ".codex" "Codex home directory must be persisted under ~/.codex")
      (expect.persistedHomeDir config ".gemini" "Gemini home directory must be persisted under ~/.gemini")
      (expect.persistedHomeDir config ".local/state/claude-code"
        "Claude Code npm state must be persisted"
      )
      (expect.persistedHomeDir config ".local/state/codex" "Codex npm state must be persisted")
      (expect.persistedHomeDir config ".local/state/gemini" "Gemini npm state must be persisted")
      (expect.hmFileExists hm ".local/bin/gemini" "Gemini wrapper must exist")
      (expect.hmFileTextNotMatches hm ".local/bin/gemini" ".*render-agents.*"
        "Gemini wrapper must not render instructions on every launch"
      )
      (expect.xdgConfigFileExists hm "claude/CLAUDE.md" "Claude instruction root must exist")
      (expect.xdgConfigFileExists hm "claude/skills" "Claude skills symlink must exist")
      {
        assertion = !(hm.xdg.configFile."claude/skills".recursive or false);
        message = "Claude skills must stay a direct directory symlink, not a recursive materialization";
      }
      (expect.xdgConfigFileExists hm "claude/world-model" "Claude world model tree must exist")
      (expect.xdgConfigFileExists hm "claude/operational" "Claude operational knowledge tree must exist")
      (expect.activationExists hm "renderGlobalCodexAgents"
        "Global Codex AGENTS render activation must exist"
      )
      (expect.activationExists hm "renderGlobalGeminiAgents"
        "Global Gemini instruction render activation must exist"
      )
    ];
}
