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

    orchestrate = {
      toolsets = [
        "skills"
        "todo"
        "memory"
        "session_search"
        "clarify"
      ];
      mcpProfile = "orchestrate";
      reasoningEffort = "high";
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

  # Claude variants. The upstream installer owns bare `claude`; `claude-lean`
  # is the managed default. `mcpProfile`, `model`, and `env` feed the renderers.
  claudeLanes = {
    full = {
      binName = "claude-full";
      mcpProfile = "full";
    };
    lean = {
      binName = "claude-lean";
      mcpProfile = "lean";
    };
    browser = {
      binName = "claude-browser";
      mcpProfile = "browser";
    };
    # DeepSeek through the real Claude Code harness via its native
    # Anthropic-compatible endpoint. Full/default MCP profile.
    deepseek = {
      binName = "claude-deepseek";
      mcpProfile = "full";
      model = "deepseek-chat";
      env = {
        baseUrl = "https://api.deepseek.com/anthropic";
        authToken.secretName = "deepseek-api-key";
      };
    };
    # Local models through the real Claude Code harness, via the LiteLLM
    # gateway that translates Anthropic <-> OpenAI
    # (modules/services/litellm.nix). Keep `model` in sync with an entry in
    # that module's model_list.
    local = {
      binName = "claude-local";
      mcpProfile = "full";
      model = "local-chat";
      env = {
        # LiteLLM binds loopback with no master key; Claude Code still
        # requires a non-empty token, so send a dummy.
        baseUrl = "http://127.0.0.1:4000";
        authToken.literal = "sk-local";
      };
    };
  };

  # Codex variants. The lean lane owns bare `codex`; profiles and backend
  # environment details are rendered outside this registry.
  codexLanes = {
    full = {
      binName = "codex-full";
      mcpProfile = "full";
    };
    lean = {
      binName = "codex";
      mcpProfile = "lean";
    };
    browser = {
      binName = "codex-browser";
      mcpProfile = "browser";
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
