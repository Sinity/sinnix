# Agent CLI wrapper variant registry — single source for the "which
# client/backend/key-source/MCP-profile" axis, rendered by
# modules/features/dev/agents/clis.nix. Builder machinery (npm bootstrap,
# mkHermesConfig, mkClaudeCodeWrapper/mkCodexWrapper/mkHermesWrapper, the
# backend-env builders) stays in backends.nix; this file only holds the data
# each builder is parameterized with.
{
  # Hermes profile configs (~/.hermes/profiles/<name>/config.yaml, rendered
  # by mkHermesConfig) and their matching hermes-<name> wrapper
  # (mkHermesWrapper { profile = name; }). The base, non-profile `hermes`
  # command (~/.hermes/config.yaml) is not a lane — it is a single fixed
  # mkHermesConfig call in clis.nix.
  #
  # Fields:
  #   toolsets        - platform_toolsets.cli list (required).
  #   mcpProfile       - mcp-registry.nix profile tier feeding mcp_servers;
  #                      defaults to "evidence" when omitted.
  #   reasoningEffort  - defaults to "medium" in mkHermesConfig when omitted.
  #   delegation       - overrides layered onto mkHermesConfig's default
  #                      { max_iterations=100; max_concurrent_children=3;
  #                      max_spawn_depth=1; } via `//`.
  #   voiceEnabled     - defaults to true in mkHermesConfig when omitted.
  #   model            - overrides mkHermesConfig's default
  #                      { default="gpt-5.6-terra"; provider="openai-codex"; }.
  #                      For custom-endpoint lanes (local, sampler) this also
  #                      supplies `model.base_url`, reused by the wrapper's
  #                      OPENAI_BASE_URL export so the URL has one source.
  #   apiKeyLiteral    - static (non-secret) OPENAI_API_KEY value for
  #                      loopback gateways that need a non-empty token but
  #                      enforce no real auth (LiteLLM on 127.0.0.1).
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

    # Base-model exploration profile. Points at the roster's MoE reasoning
    # tier, NOT a true base model: no verified local base-model ollama/GGUF
    # source exists (a wrong tag fails the boot-time pull), and the only
    # confirmed big base-model API (Hyperbolic Llama-3.1-405B-BASE) needs a
    # funded external account. Promote this lane in place once either lands.
    # Minimal toolset: a sampler explores completions, not web/file/delegation.
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

  # Claude Code variants (mkClaudeCodeWrapper). `binName` is explicit data
  # because the family is not regular: every wrapper is `claude-<lane>`, but
  # the bare `claude` name is unsafe to own (the upstream installer clobbers
  # it, see clis.nix), so the default lane's file is `claude-lean` with a
  # `claude` shell alias pointing at it.
  #
  # `mcpProfile` selects both the mcp-registry.nix tier and the
  # `~/.config/claude/<mcp file>.json` basename ("full" -> "mcp", otherwise
  # "mcp-<mcpProfile>"); deepseek/local intentionally reuse the "full" tier
  # (same MCP surface, different backend).
  #
  # `env`/`model` (only on deepseek/local) parameterize
  # backends.nix's mkClaudeBackendEnv: `env.baseUrl` sets ANTHROPIC_BASE_URL,
  # `env.authToken` is either `{ secretName = "<agenix secret>"; }` or
  # `{ literal = "<static token>"; }`, and `model` fans out into
  # ANTHROPIC_MODEL / ANTHROPIC_DEFAULT_*_MODEL / CLAUDE_CODE_SUBAGENT_MODEL.
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

  # Codex variants (mkCodexWrapper). Unlike Claude, the "lean"/default lane
  # has no naming conflict, so its file is the bare client name.
  #
  # `mcpProfile` is passed straight through as the codex `--profile` arg and
  # SINNIX_CODEX_PROFILE value; the matching `<profile>.config.toml` (model +
  # model_provider + full MCP table) is generated in mcp.nix's
  # client-profiles.nix, not here.
  #
  # `env` (only on deepseek/local) parameterizes backends.nix's
  # mkCodexBackendEnv: `varName` is the single env var the layered
  # config.toml's `model_providers.<provider>.env_key` expects, sourced
  # either from `secretName` (agenix) or a static `literal`.
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

  # Deliberate non-lanes: single fixed wrappers with no variant axis to
  # register, left hardcoded in clis.nix.
  #   - gemini            - one CLI, one profile, no backend/key variants.
  #   - grok-sinnix        - vendor-managed Grok CLI passthrough.
  #   - agy-sinnix         - vendor-managed Antigravity CLI passthrough.
  #   - hermes-acp         - alternate hermes entrypoint (`hermes-acp`
  #                          binary), not a profile.
  #   - hermes-update      - maintenance script (git pull + uv sync), not a
  #                          launcher.
}
