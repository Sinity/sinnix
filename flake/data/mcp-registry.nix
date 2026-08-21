{ lib }:
let
  pruneAttrs = lib.filterAttrs (_: value: value != null && value != [ ] && value != { });

  # Every server describes itself in one line, the same contract script
  # frontmatter and the module factories carry: the capability index
  # (/etc/sinnix/capability-index.json) renders this registry for a reader who
  # is asking what "firecrawl" even is, and a nameless row there is
  # worse than absent. Enforced where it is consumed, so a missing description
  # is a build failure rather than a blank cell on the hub.
  undescribed = lib.attrNames (
    lib.filterAttrs (_: server: (server.description or "") == "") rawRegistry
  );
  registry = lib.throwIf (undescribed != [ ]) (
    "flake/data/mcp-registry.nix: these servers have no description: "
    + lib.concatStringsSep ", " undescribed
  ) rawRegistry;

  rawRegistry = {
    context7 = {
      description = "Current third-party library and API documentation, resolved by library id";
      transport = "http";
      tier = "remote-core";
      url = "https://mcp.context7.com/mcp";
      clients = [
        "claude"
        "codex"
        "gemini"
        "antigravity"
        "hermes"
      ];
      codex.bearer_token_env_var = "CONTEXT7_API_KEY";
      hermes.headers.Authorization = "Bearer \${CONTEXT7_API_KEY}";
    };

    github = {
      description = "GitHub issues, pull requests, and repository operations";
      transport = "stdio";
      tier = "remote-core";
      command = "npx";
      args = [
        "-y"
        "@modelcontextprotocol/server-github"
      ];
      env = {
        GITHUB_PERSONAL_ACCESS_TOKEN = "\${GITHUB_TOKEN}";
      };
      clients = [
        "claude"
        "codex"
        "gemini"
        "antigravity"
        "hermes"
      ];
    };

    agent-control = {
      description = "Local-agent-control profile of the Sinnix agent gateway: inspect and steer agent jobs";
      transport = "stdio";
      tier = "agent-control";
      command = "sinnix-agent-control-mcp";
      clients = [
        "claude"
        "codex"
        "gemini"
        "antigravity"
        "hermes"
      ];
    };

    firecrawl = {
      description = "Web page scraping and crawling for readable page content";
      transport = "stdio";
      tier = "browser-mcp";
      command = "mcp-firecrawl";
      clients = [
        "claude"
        "hermes"
      ];
    };

    lynchpin = {
      description = "Personal analysis hub: cross-source timelines, correlations, and materialized products";
      transport = "stdio";
      tier = "deep-evidence";
      command = "mcp-lynchpin";
      env = {
        LYNCHPIN_REPO_ROOT = "/realm/project/sinity-lynchpin";
        LYNCHPIN_LOCAL_ROOT = "/realm/project/sinity-lynchpin/.lynchpin";
      };
      clients = [
        "codex"
        "claude"
        "gemini"
        "antigravity"
        "hermes"
      ];
    };

    polylogue = {
      description = "AI chat archive: search and read past Claude, Codex, and ChatGPT sessions";
      transport = "stdio";
      tier = "recall";
      command = "mcp-polylogue";
      profiles = {
        full.args = [
          "--role"
          "write"
        ];
        evidence.args = [
          "--role"
          "write"
        ];
        browser.args = [
          "--role"
          "write"
        ];
        antigravity.args = [
          "--role"
          "write"
        ];
        lean.args = [
          "--role"
          "read"
        ];
      };
      clients = [
        "codex"
        "claude"
        "gemini"
        "antigravity"
        "hermes"
      ];
    };

    sinex = {
      description = "Sinex capture platform: query captured events and their substrate";
      transport = "stdio";
      tier = "recall";
      command = "mcp-sinex";
      clients = [
        "codex"
        "claude"
        "gemini"
        "antigravity"
        "hermes"
      ];
    };

    chrome-devtools = {
      description = "Chrome DevTools control of the operator's own browser";
      transport = "stdio";
      tier = "browser-mcp";
      command = "mcp-chrome-devtools";
      clients = [
        "claude"
        "codex"
        "gemini"
      ];
    };

  };

  profileTiers = {
    lean = [
      "remote-core"
      "recall"
    ];
    evidence = [
      "remote-core"
      "recall"
      "deep-evidence"
    ];
    full = [
      "remote-core"
      "recall"
      "deep-evidence"
    ];
    browser = [
      "remote-core"
      "recall"
      "deep-evidence"
      "browser-mcp"
    ];
    orchestrate = [
      "remote-core"
      "recall"
      "deep-evidence"
      "agent-control"
    ];
    # Antigravity blocks print-mode startup while any MCP remains pending.
    # Keep the ordinary coding and orchestration surface, but leave slow
    # deep-evidence servers to clients with bounded MCP startup handling.
    antigravity = [
      "remote-core"
      "recall"
      "agent-control"
    ];
  };

  selectClientServersForProfile =
    profile: client:
    let
      tiers = profileTiers.${profile};
    in
    lib.mapAttrs
      (
        _: server:
        let
          profileOverride = (server.profiles or { }).${profile} or { };
        in
        lib.recursiveUpdate server profileOverride
      )
      (
        lib.filterAttrs (
          _: server: builtins.elem client server.clients && builtins.elem (server.tier or "full") tiers
        ) registry
      );

  selectClientServers = selectClientServersForProfile "full";

  # Claude Code mcpServers entry.
  renderClaudeServer =
    _name: server:
    pruneAttrs (
      if server.transport == "http" then
        {
          type = "http";
          inherit (server) url;
        }
      else
        let
          claude = server.claude or { };
        in
        {
          inherit (server) command;
          args = claude.args or server.args or [ ];
          env = claude.env or server.env or { };
        }
    );

  # Codex `[mcp_servers.<name>]` TOML entry as a Nix attrset (caller renders TOML).
  renderCodexServer =
    _name: server:
    pruneAttrs (
      if server.transport == "http" then
        let
          codex = server.codex or { };
        in
        {
          inherit (server) url;
          bearer_token_env_var = codex.bearer_token_env_var or null;
        }
      else
        let
          codex = server.codex or { };
        in
        {
          inherit (server) command;
          args = codex.args or server.args or [ ];
          env = codex.env or server.env or { };
          startup_timeout_sec = codex.startup_timeout_sec or null;
        }
    );

  # Gemini settings.json mcpServers entry.
  renderGeminiServer =
    _name: server:
    pruneAttrs (
      if server.transport == "http" then
        let
          gemini = server.gemini or { };
        in
        {
          httpUrl = server.url;
          headers = gemini.headers or server.headers or { };
        }
      else
        let
          gemini = server.gemini or { };
        in
        {
          inherit (server) command;
          args = gemini.args or server.args or [ ];
          env = gemini.env or server.env or { };
        }
    );

  # Antigravity CLI uses the same stdio shape as Gemini, but names remote
  # endpoints `serverUrl` in ~/.gemini/config/mcp_config.json.
  renderAntigravityServer =
    _name: server:
    pruneAttrs (
      if server.transport == "http" then
        let
          antigravity = server.antigravity or { };
        in
        {
          serverUrl = server.url;
          headers = antigravity.headers or server.headers or { };
        }
      else
        let
          antigravity = server.antigravity or { };
        in
        {
          inherit (server) command;
          args = antigravity.args or server.args or [ ];
          env = antigravity.env or server.env or { };
        }
    );

  # Hermes mcp_servers entry.  Its YAML format accepts the native stdio and
  # streamable-HTTP shapes, including config-level ${VAR} substitution.
  renderHermesServer =
    _name: server:
    pruneAttrs (
      if server.transport == "http" then
        let
          hermes = server.hermes or { };
        in
        {
          inherit (server) url;
          headers = hermes.headers or server.headers or { };
        }
      else
        let
          hermes = server.hermes or { };
        in
        {
          inherit (server) command;
          args = hermes.args or server.args or [ ];
          env = hermes.env or server.env or { };
        }
    );

in
{
  inherit
    registry
    profileTiers
    selectClientServers
    selectClientServersForProfile
    renderClaudeServer
    renderCodexServer
    renderGeminiServer
    renderAntigravityServer
    renderHermesServer
    ;
}
