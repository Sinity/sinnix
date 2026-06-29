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
      # `claude-full` (NOT a bare ~/.local/bin/claude): Claude Code's native
      # local-installer owns the bare path and clobbers it, so the wrapper is
      # suffixed and the `claude` shell alias points to it.
      (expect.hmFileExists hm ".local/bin/claude-full" "Claude full wrapper must exist")
      {
        assertion = !(hm.home.file ? ".local/bin/claude");
        message = "Bare ~/.local/bin/claude must not be declared — it collides with Claude Code's local-installer";
      }
      (expect.hmFileExists hm ".local/bin/claude-lean" "Claude lean wrapper must exist")
      (expect.hmFileExists hm ".local/bin/claude-browser" "Claude browser wrapper must exist")
      (expect.hmFileExists hm ".local/bin/claude-deepseek" "Claude DeepSeek wrapper must exist")
      (expect.hmFileExists hm ".local/bin/claude-local" "Claude local-model wrapper must exist")
      (expect.hmFileTextContains hm ".local/bin/claude-deepseek" "api.deepseek.com/anthropic"
        "claude-deepseek must target DeepSeek's Anthropic-compatible endpoint"
      )
      (expect.hmFileTextContains hm ".local/bin/claude-local" "127.0.0.1:4000"
        "claude-local must target the LiteLLM gateway"
      )
      {
        assertion = lib.any (pkg: lib.getName pkg == "sinnix-scope") hm.home.packages;
        message = "sinnix-scope must be in the user profile so wrapper runtime fallbacks are real";
      }
      (expect.hmFileExists hm ".local/bin/codex" "Codex wrapper must exist")
      (expect.hmFileExists hm ".local/bin/codex-lean" "Codex lean wrapper must exist")
      (expect.hmFileExists hm ".local/bin/codex-full" "Codex full wrapper must exist")
      (expect.hmFileExists hm ".local/bin/codex-browser" "Codex browser wrapper must exist")
      (expect.hmFileExists hm ".local/bin/codex-deepseek" "Codex DeepSeek wrapper must exist")
      (expect.hmFileExists hm ".local/bin/codex-local" "Codex local-model wrapper must exist")
      (expect.hmFileTextContains hm ".local/bin/codex-deepseek" "--profile deepseek"
        "codex-deepseek must layer the deepseek profile"
      )
      (expect.hmFileTextContains hm ".local/bin/codex-local" "--profile local"
        "codex-local must layer the local profile"
      )
      (expect.hmFileTextContains hm ".local/bin/codex" "--profile full"
        "default Codex must retain the full MCP profile"
      )
      (expect.hmFileTextContains hm ".local/bin/codex-full" "--profile full"
        "codex-full must retain the deliberate full MCP profile"
      )
      (expect.hmFileTextNotMatches hm ".local/bin/codex" ".*render-agents.*"
        "Codex wrapper must not render AGENTS on every launch"
      )
      (expect.hmFileTextNotMatches hm ".local/bin/claude-full" ".*agent-fhs.*"
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
      (expect.xdgConfigFileExists hm "claude/skills" "Claude curated skills symlink must exist")
      {
        assertion = !(hm.xdg.configFile."claude/skills".recursive or false);
        message = "Claude skills must stay a direct curated directory symlink";
      }
      {
        assertion = !(hm.xdg.configFile ? "claude/skills/persona");
        message = "Claude persona skill must not be exposed by default";
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
