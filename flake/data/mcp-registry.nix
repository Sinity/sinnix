{ lib }:
let
  pruneAttrs = lib.filterAttrs (_: value: value != null && value != [ ] && value != { });

  registry = {
    context7 = {
      transport = "http";
      tier = "remote-core";
      url = "https://mcp.context7.com/mcp";
      clients = [
        "claude"
        "codex"
        "gemini"
      ];
      codex.bearer_token_env_var = "CONTEXT7_API_KEY";
    };

    github = {
      transport = "http";
      tier = "remote-core";
      url = "https://api.githubcopilot.com/mcp/";
      clients = [
        "claude"
        "codex"
        "gemini"
      ];
      codex.bearer_token_env_var = "GITHUB_TOKEN";
      gemini.headers.Authorization = "Bearer \${GITHUB_TOKEN}";
    };

    codebase-memory-mcp = {
      transport = "stdio";
      tier = "code-semantic";
      command = "codebase-memory-mcp";
      clients = [
        "codex"
        "claude"
        "gemini"
      ];
    };

    serena = {
      transport = "stdio";
      tier = "code-semantic";
      command = "serena";
      args = [
        "start-mcp-server"
        "--project-from-cwd"
        "--context=ide"
      ];
      clients = [
        "codex"
        "claude"
        "gemini"
      ];
      claude.args = [
        "start-mcp-server"
        "--project-from-cwd"
        "--context=claude-code"
      ];
      codex = {
        startup_timeout_sec = 15;
        args = [
          "start-mcp-server"
          "--project-from-cwd"
          "--context=codex"
        ];
      };
    };

    firecrawl = {
      transport = "stdio";
      tier = "browser-mcp";
      command = "mcp-firecrawl";
      clients = [
        "claude"
      ];
    };

    lynchpin = {
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
      ];
    };

    polylogue = {
      transport = "stdio";
      tier = "recall";
      command = "mcp-polylogue";
      clients = [
        "codex"
        "claude"
        "gemini"
      ];
    };

    chrome-devtools = {
      transport = "stdio";
      tier = "browser-mcp";
      command = "mcp-chrome-devtools";
      clients = [
        "claude"
        "codex"
        "gemini"
      ];
    };

    chrome-devtools-private = {
      transport = "stdio";
      tier = "browser-mcp";
      command = "mcp-chrome-devtools-private";
      clients = [
        "claude"
        "codex"
        "gemini"
      ];
    };

    chrome-devtools-private-visible = {
      transport = "stdio";
      tier = "browser-mcp";
      command = "mcp-chrome-devtools-private-visible";
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
      "code-semantic"
    ];
    browser = [
      "remote-core"
      "recall"
      "deep-evidence"
      "code-semantic"
      "browser-mcp"
    ];
  };

  selectClientServersForProfile =
    profile: client:
    let
      tiers = profileTiers.${profile};
    in
    lib.filterAttrs (
      _: server: builtins.elem client server.clients && builtins.elem (server.tier or "full") tiers
    ) registry;

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
    ;
}
