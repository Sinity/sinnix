# Agent CLI wrapper variant registry — single source for the "which
# client/backend/key-source/MCP-profile" axis, rendered by
# modules/features/dev/agents/clis.nix by mapping over this data instead of
# hand-enumerating each wrapper. Builder machinery (npm bootstrap, mkHermesConfig,
# mkClaudeCodeWrapper/mkCodexWrapper/mkHermesWrapper, the backend-env
# builders) stays in backends.nix; this file only holds the data each
# builder is parameterized with. Pure data, no `lib` needed — mirrors
# flake/data/shared-agent-skills.nix's plain-value shape rather than
# mcp-registry.nix/local-models.nix's `{ lib }: ...` shape, since nothing
# here needs list/attrset helpers at the data-authoring layer (clis.nix does
# the mapAttrs-ing).
{
  # Hermes profile configs (~/.hermes/profiles/<name>/config.yaml, rendered
  # by mkHermesConfig) and their matching hermes-<name> wrapper
  # (mkHermesWrapper { profile = name; }). The base, non-profile `hermes`
  # command (~/.hermes/config.yaml) is not a lane — it is a single fixed
  # mkHermesConfig call in clis.nix, since there is nothing to vary it
  # against.
  #
  # Fields:
  #   toolsets        - platform_toolsets.cli list (required).
  #   mcpProfile       - mcp-registry.nix profile tier feeding mcp_servers;
  #                      defaults to "evidence" (mirrors the pre-registry
  #                      default arg of mkHermesConfig) when omitted.
  #   reasoningEffort  - defaults to "medium" in mkHermesConfig when omitted.
  #   delegation       - overrides layered onto mkHermesConfig's default
  #                      { max_iterations=100; max_concurrent_children=3;
  #                      max_spawn_depth=1; } via `//`.
  #   voiceEnabled     - defaults to true in mkHermesConfig when omitted.
  #   model            - overrides mkHermesConfig's default
  #                      { default="gpt-5.6-terra"; provider="openai-codex"; }.
  #                      For custom-endpoint lanes (muse, local) this also
  #                      supplies `model.base_url`, reused by the wrapper's
  #                      OPENAI_BASE_URL export so the URL has one source.
  #   preludeSecret    - agenix secret name resolved into OPENAI_API_KEY via
  #                      lib.sinnix.mkSecretLookup before launch (custom
  #                      OpenAI-compatible endpoints prefer OPENAI_API_KEY —
  #                      hermes-agent issue #560).
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

    # Muse Spark contributor tier via the Vercel AI Gateway. Meta gates the
    # tier server-side ("select countries") and does not serve it to this
    # account directly; the gateway carries it at contributor list prices.
    muse = {
      toolsets = [ "hermes-cli" ];
      model = {
        default = "meta/muse-spark-1.2-contributor";
        provider = "custom";
        base_url = "https://ai-gateway.vercel.sh/v1";
      };
      preludeSecret = "vercel-ai-gateway-key";
    };

    # Local Ollama hub via the LiteLLM gateway; model names live in
    # litellm.nix's model_list. A profile (not an imperative `hermes config
    # set` at launch) so the default config is never mutated.
    local = {
      toolsets = [ "hermes-cli" ];
      model = {
        default = "local-chat";
        provider = "custom";
        base_url = "http://127.0.0.1:4000/v1";
      };
      apiKeyLiteral = "sk-local";
    };

    # sinnix-z7v Hermes power-up, profiles 2/3 of 3 (director deferred — see
    # below). Both point at the roster's existing MoE reasoning tiers, NOT
    # true base models: a real local base-model pull needs a verified
    # ollama/GGUF source (the only community tag found, kimsan0622/Qwen3-8B-
    # Base, is unverified and a wrong tag fails a boot-time pull loudly, not
    # silently — real risk, not laziness) and the alternative (Hyperbolic's
    # Llama-3.1-405B-BASE API, the only confirmed big-base-model API per
    # 2026-08-11 recon) needs a funded external account this module can't
    # create. Both are legitimate blockers, not deferred-for-convenience;
    # promote either lane in place here once one is resolved.
    sampler = {
      # Base-model exploration profile: minimal toolset (a sampler explores
      # completions, it doesn't need web/file/delegation), MoE reasoning
      # tier standing in for true base access until the above resolves.
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
      # Research twin wired to nx0's evidence-and-verification pipeline
      # (dots/_ai/workflows/deep-research.mjs) via the "research" MCP tier
      # and delegation toolset — nx0 runs as a Workflow the operator invokes
      # separately; this profile is oracle's own interactive counterpart,
      # matching research's shape since both need the full evidence stack.
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

  # Claude Code variants (mkClaudeCodeWrapper). `binName` is data, not
  # mechanically derived from the lane key, because the family is not
  # regular: every wrapper is named `claude-<lane>` EXCEPT the upstream
  # installer-clobber workaround already documented in clis.nix — the
  # `claude` binary name is unsafe to own, so the "lean"/default lane's file
  # is `claude-lean` and a separate `claude` shell alias points at it
  # (rendered from claudeLanes + one explicit remap in clis.nix, not a
  # per-lane self-alias like the other four).
  #
  # `mcpProfile` selects both the mcp-registry.nix tier and the
  # `~/.config/claude/<mcp file>.json` basename ("full" -> "mcp", otherwise
  # "mcp-<mcpProfile>"); deepseek/local intentionally reuse the "full" tier
  # (same MCP surface, different backend).
  #
  # `env`/`model` (only on deepseek/local) parameterize
  # backends.nix's mkClaudeBackendEnv: `env.baseUrl` sets ANTHROPIC_BASE_URL,
  # `env.authToken` is either `{ secretName = "<agenix secret>"; }` (read via
  # the same secret-resolution shape as lib.sinnix.mkSecretLookup) or
  # `{ literal = "<static token>"; }` for the LiteLLM loopback gateway (no
  # real key enforced, but Claude Code requires a non-empty token), and
  # `model` fans out into ANTHROPIC_MODEL / ANTHROPIC_DEFAULT_*_MODEL /
  # CLAUDE_CODE_SUBAGENT_MODEL.
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
    # (modules/services/litellm.nix). Full/default MCP profile. Model names
    # are defined in that module's model_list; keep `model` in sync with an
    # entry there.
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
  # has no naming conflict, so its file is the bare client name; `binName`
  # still carries this explicitly for the same reason as claudeLanes (no
  # single mechanical rule covers both the bare-name default and the
  # `codex-<lane>` others cleanly).
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

  # Muse lanes: thin passthrough wrappers around vendor-managed/gateway
  # scripts (the scripts themselves stay in scripts/, packaged normally).
  # `script` is both the scriptPkgs attribute name and the packaged binary
  # name for both lanes today.
  museLanes = {
    muse-code = {
      script = "sinnix-muse-code-bootstrap";
    };
    muse-contrib = {
      script = "muse-contrib";
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
