# Agent launcher profile registry. Renderers and wrapper mechanics live in
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

    # Local models through LiteLLM; names live in local-models.nix.
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
      # Same tools and delegation limits as research, retained as a named
      # interactive profile.
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

  # The private npm prefix owns each upstream executable; the managed command
  # selects the default MCP set.
  claudeProfiles = {
    default = {
      binName = "claude";
      mcpProfile = "default";
    };
  };

  # The default Codex command reads the generated system config.
  codexProfiles = {
    default = {
      binName = "codex";
      mcpProfile = "default";
    };
  };

  # Fixed, non-variant wrappers stay in clis.nix.
}
