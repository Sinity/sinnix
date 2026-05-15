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
      forgeConfigText = builtins.readFile (inputs.self + "/dots/forge/.forge.toml");
      forgeMcpConfig = builtins.fromJSON (managedEntryText hm.home.file."forge/.mcp.json");
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
      (expect.hmFileTextContainsAll hm ".local/bin/codex" [
        ''scope_bin="''
        "/bin/sinnix-scope"
        "command -v sinnix-scope"
        ''"$scope_bin" agent --''
      ] "Codex wrapper must use the shared Sinnix placement helper with a runtime fallback")
      (expect.hmFileTextNotMatches hm ".local/bin/codex" ".*render-agents.*"
        "Codex wrapper must not render AGENTS on every launch"
      )
      (expect.hmPackagedWrapper hm ".local/bin/forge" {
        envVar = "FORGE_BIN";
        binaryFragments = [ "/bin/forge" ];
        forbidRegexes = [ "curl -fsSL" ];
      } "Forge wrapper must launch the packaged binary directly")
      (expect.hmFileExists hm ".local/bin/forge" "Forge wrapper must exist")
      (expect.hmFileTextContainsAll hm ".local/bin/forge" [
        ''scope_bin="''
        "/bin/sinnix-scope"
        "command -v sinnix-scope"
        ''"$scope_bin" agent --''
      ] "Forge wrapper must use the shared Sinnix placement helper with a runtime fallback")
      (expect.activationExists hm "renderGlobalForgeAgents"
        "Global Forge AGENTS render activation must exist"
      )
      (expect.hmFileExists hm "forge/skills" "Forge skill root must be linked from the shared skill tree")
      {
        assertion = !(hm.home.file."forge/skills".recursive or false);
        message = "Forge skill root must stay a direct directory symlink, not a recursive materialization";
      }
      (expect.textContains hm.programs.zsh.initContent "export FORGE_BIN=\"$HOME/.local/bin/forge\""
        "Zsh init must source Forge via the managed wrapper path"
      )
      (expect.hmFileExists hm "forge/.forge.toml"
        "Forge config must be managed under ~/forge/.forge.toml"
      )
      (expect.textContainsAll forgeConfigText [
        "provider_id = \"codex\""
        "model_id = \"gpt-5.5\""
        "auto_dump = \"json\""
        "auto_open_dump = false"
      ] "Forge config must preserve the Codex session defaults and dump settings")
      (expect.textContainsAll forgeConfigText [
        "debug_requests = \""
        "/forge/logs/requests\""
        "max_conversations = 1000000"
        "auto_update = false"
        "frequency = \"weekly\""
      ] "Forge config must keep durable request logs and disable self-updates")
      (expect.textContainsAll forgeConfigText [
        "max_fetch_chars = 75000"
        "max_file_read_batch_size = 64"
        "max_parallel_file_reads = 64"
        "max_read_lines = 4000"
        "max_requests_per_turn = 100"
        "max_tool_failure_per_turn = 5"
        "tool_timeout_secs = 600"
      ] "Forge config must keep the bounded runtime guardrails")
      (expect.textNotMatches forgeConfigText ".*custom_history_path.*"
        "Forge config must rely on Forge's native history storage path"
      )
      (expect.textNotMatches forgeConfigText ".*[[]compact[]].*"
        "Forge config must not override upstream compaction defaults"
      )
      (expect.persistedHomeDir config "forge" "Forge home directory must be persisted under ~/forge")
      (expect.persistedHomeDir config ".config/claude"
        "Claude config directory must be persisted under ~/.config/claude"
      )
      (expect.persistedHomeDir config ".codex" "Codex home directory must be persisted under ~/.codex")
      (expect.persistedHomeDir config ".gemini" "Gemini home directory must be persisted under ~/.gemini")
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
      (expect.hmPackagedWrapper hm ".local/bin/gemini" {
        envVar = "GEMINI_BIN";
        binaryFragments = [ "/bin/gemini" ];
        forbidRegexes = [
          "npx"
          "bundle/index\\.js"
        ];
      } "Gemini wrapper must launch the packaged binary directly")
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
