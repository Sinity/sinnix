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
      managedEntryText =
        entry:
        if entry ? text && entry.text != null then
          entry.text
        else if entry ? source && entry.source != null then
          builtins.readFile entry.source
        else
          "";
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
      deepseekWrapperText = managedEntryText hm.home.file.".local/bin/deepseek";
      sharedSkillSelfLinks = findSelfReferentialLinks (inputs.self + "/dots/_ai/skills");
    in
    [
      {
        assertion = builtins.match ".*\\$\\*.*" (hm.home.file.".local/bin/claude-team".text or "") == null;
        message = "Claude team wrapper must not flatten arguments via $*";
      }
      {
        assertion = sharedSkillSelfLinks == [ ];
        message = "Shared skills tree must not contain self-referential symlinks: ${lib.concatStringsSep ", " sharedSkillSelfLinks}";
      }
      (expect.hmFileExists hm ".local/bin/claude" "Claude wrapper must exist")
      (expect.hmFileExists hm ".local/bin/claude-opus" "Claude Opus wrapper must exist")
      (expect.hmFileExists hm ".local/bin/claude-sonnet" "Claude Sonnet wrapper must exist")
      (expect.hmFileExists hm ".local/bin/claude-lite" "Claude bare/no-MCP wrapper must exist")
      (expect.hmFileTextContainsAll hm ".local/bin/claude" [
        "--mcp-config"
        "--strict-mcp-config"
      ] "Default Claude wrapper must use only the managed MCP config")
      (expect.hmFileTextContainsAll hm ".local/bin/claude-opus" [
        "--model"
        "opus"
        "--effort"
        "high"
      ] "Claude Opus wrapper must force the Opus high-effort profile")
      (expect.hmFileTextContainsAll hm ".local/bin/claude-sonnet" [
        "--model"
        "sonnet"
        "--effort"
        "medium"
      ] "Claude Sonnet wrapper must force the Sonnet medium-effort profile")
      (expect.hmFileTextContainsAll hm ".local/bin/claude-lite" [
        "--bare"
      ] "Claude lite wrapper must run bare")
      (expect.hmFileTextNotMatches hm ".local/bin/claude-lite" ".*--mcp-config.*"
        "Claude lite wrapper must not attach MCP servers"
      )
      {
        assertion = lib.any (pkg: lib.getName pkg == "sinnix-scope") hm.home.packages;
        message = "sinnix-scope must be in the user profile so wrapper runtime fallbacks are real";
      }
      (expect.hmFileTextContainsAll hm ".local/bin/claude" [
        ''scope_bin="''
        "/bin/sinnix-scope"
        "command -v sinnix-scope"
        ''"$scope_bin" agent --''
      ] "Claude wrapper must use the shared Sinnix placement helper with a runtime fallback")
      (expect.hmFileExists hm ".local/bin/deepseek" "DeepSeek wrapper must exist")
      (expect.hmFileTextContainsAll hm ".local/bin/deepseek" [
        ''scope_bin="''
        "/bin/sinnix-scope"
        "command -v sinnix-scope"
        ''"$scope_bin" agent --''
      ] "DeepSeek wrapper must use the shared Sinnix placement helper with a runtime fallback")
      {
        assertion =
          lib.hasInfix ''DEEPSEEK_MODEL="deepseek-v4-pro[1m]"'' deepseekWrapperText
          && lib.hasInfix ''export ANTHROPIC_MODEL="$DEEPSEEK_MODEL"'' deepseekWrapperText
          && lib.hasInfix ''export ANTHROPIC_DEFAULT_OPUS_MODEL="$DEEPSEEK_MODEL"'' deepseekWrapperText
          && lib.hasInfix ''export ANTHROPIC_DEFAULT_SONNET_MODEL="$DEEPSEEK_MODEL"'' deepseekWrapperText
          && lib.hasInfix ''export ANTHROPIC_DEFAULT_HAIKU_MODEL="$DEEPSEEK_MODEL"'' deepseekWrapperText
          && lib.hasInfix ''export CLAUDE_CODE_SUBAGENT_MODEL="$DEEPSEEK_MODEL"'' deepseekWrapperText
          && !(lib.hasInfix "deepseek-v4-flash" deepseekWrapperText);
        message = "DeepSeek wrapper must force v4 pro 1m for default, opus, sonnet, haiku, and subagents";
      }
      (expect.hmFileExists hm ".local/bin/codex" "Codex wrapper must exist")
      (expect.hmFileExists hm ".local/bin/codex-fast" "Codex fast profile wrapper must exist")
      (expect.hmFileExists hm ".local/bin/codex-deep" "Codex deep profile wrapper must exist")
      (expect.hmFileExists hm ".local/bin/codex-max" "Codex max profile wrapper must exist")
      (expect.hmFileExists hm ".local/bin/codex-spark" "Codex Spark profile wrapper must exist")
      (expect.hmFileExists hm ".local/bin/codex-spark-xhigh"
        "Codex Spark xhigh profile wrapper must exist"
      )
      (expect.hmFileTextContainsAll hm ".local/bin/codex-fast" [
        "--profile"
        "fast"
      ] "Codex fast wrapper must select the fast profile")
      (expect.hmFileTextContainsAll hm ".local/bin/codex-deep" [
        "--profile"
        "deep"
      ] "Codex deep wrapper must select the deep profile")
      (expect.hmFileTextContainsAll hm ".local/bin/codex-max" [
        "--profile"
        "max"
      ] "Codex max wrapper must select the max profile")
      (expect.hmFileTextContainsAll hm ".local/bin/codex-spark" [
        "--profile"
        "spark_medium"
      ] "Codex Spark wrapper must select the Spark medium profile")
      (expect.hmFileTextContainsAll hm ".local/bin/codex-spark-xhigh" [
        "--profile"
        "spark_xhigh"
      ] "Codex Spark xhigh wrapper must select the Spark xhigh profile")
      (expect.hmFileTextContainsAll hm ".local/bin/codex" [
        ''scope_bin="''
        "/bin/sinnix-scope"
        "command -v sinnix-scope"
        ''"$scope_bin" agent --''
      ] "Codex wrapper must use the shared Sinnix placement helper with a runtime fallback")
      (expect.hmFileTextNotMatches hm ".local/bin/codex" ".*render-agents.*"
        "Codex wrapper must not render AGENTS on every launch"
      )
      (expect.hmFileTextContainsAll hm ".local/bin/codex" [
        "npm install -g @openai/codex"
        ''run_agent_scoped "$STATE/launch.sh"''
      ] "Codex wrapper must bootstrap @openai/codex without wrapping launches in FHS")
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
      (expect.hmFileTextContainsAll hm ".local/bin/gemini" [
        ''scope_bin="''
        "/bin/sinnix-scope"
        "command -v sinnix-scope"
        ''"$scope_bin" agent --''
      ] "Gemini wrapper must use the shared Sinnix placement helper with a runtime fallback")
      (expect.hmFileTextNotMatches hm ".local/bin/gemini" ".*render-agents.*"
        "Gemini wrapper must not render instructions on every launch"
      )
      (expect.hmFileTextContainsAll hm ".local/bin/gemini" [
        "npm install -g @google/gemini-cli"
        ''run_agent_scoped "$STATE/launch.sh"''
      ] "Gemini wrapper must bootstrap @google/gemini-cli without wrapping launches in FHS")
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
