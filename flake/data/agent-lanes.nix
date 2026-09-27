# Agent CLI lane registry. Renderers and wrapper mechanics live in
# modules/features/dev/agents/; this file owns only their variants.
{
  # Profile config and matching `hermes-<name>` wrapper. The base `hermes`
  # command is fixed in clis.nix. Builder defaults stay with the builder.
  hermesProfiles = {
    research = {
      toolsets = [
        "web"
        "browser"
        "file"
        "skills"
        "todo"
        "memory"
        "session_search"
        "code_execution"
        "delegation"
        "clarify"
      ];
      mcpProfile = "browser";
      reasoningEffort = "high";
      delegation = {
        max_iterations = 60;
        max_concurrent_children = 6;
        max_spawn_depth = 1;
      };
      voiceEnabled = false;
    };

    mirror = {
      toolsets = [
        "skills"
        "todo"
        "memory"
        "session_search"
        "clarify"
        "tts"
      ];
    };

    # Local Ollama hub via the LiteLLM gateway; model names live in
    # litellm.nix's model_list.
    local = {
      toolsets = [ "hermes-cli" ];
      model = {
        default = "local-chat";
        provider = "custom";
        base_url = "http://127.0.0.1:4000/v1";
      };
      apiKeyLiteral = "sk-local";
    };

    # Completion sampler, deliberately without web, file, or delegation tools.
    sampler = {
      toolsets = [ "hermes-cli" ];
      model = {
        default = "local-thinker";
        provider = "custom";
        base_url = "http://127.0.0.1:4000/v1";
      };
      apiKeyLiteral = "sk-local";
      voiceEnabled = false;
    };

    oracle = {
      # Interactive counterpart to the nx0 deep-research Workflow
      # (dots/_ai/workflows/deep-research.mjs); mirrors the `research`
      # profile's shape since both need the full evidence stack.
      toolsets = [
        "web"
        "browser"
        "file"
        "skills"
        "todo"
        "memory"
        "session_search"
        "code_execution"
        "delegation"
        "clarify"
      ];
      mcpProfile = "browser";
      reasoningEffort = "high";
      delegation = {
        max_iterations = 60;
        max_concurrent_children = 6;
        max_spawn_depth = 1;
      };
      voiceEnabled = false;
    };
  };

  # Claude variants. The private npm prefix owns the upstream executable;
  # the managed `claude` command selects the default MCP set.
  # `mcpProfile`, `model`, and `env` feed the renderers.
  claudeLanes = {
    default = {
      binName = "claude";
      mcpProfile = "default";
    };
  };

  # The default Codex command reads the generated system config. Only the
  # local and DeepSeek variants select native backend profiles.
  codexLanes = {
    default = {
      binName = "codex";
      mcpProfile = "default";
    };
    deepseek = {
      binName = "codex-deepseek";
      mcpProfile = "deepseek";
      env = {
        varName = "DEEPSEEK_API_KEY";
        secretName = "deepseek-api-key";
      };
    };
    local = {
      binName = "codex-local";
      mcpProfile = "local";
      env = {
        varName = "LITELLM_LOCAL_KEY";
        literal = "sk-local";
      };
    };
  };

  # Fixed, non-variant wrappers stay in clis.nix.
}
