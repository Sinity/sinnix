{ lib }:
let
  pruneAttrs = lib.filterAttrs (_: value: value != null && value != [ ] && value != { });

  registry = {
    context7 = {
      transport = "http";
      url = "https://mcp.context7.com/mcp";
      clients = [
        "codex"
        "gemini"
      ];
      codex.bearer_token_env_var = "CONTEXT7_API_KEY";
    };

    github = {
      transport = "http";
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
      command = "codebase-memory-mcp";
      clients = [
        "codex"
        "claude"
        "gemini"
      ];
    };

    serena = {
      transport = "stdio";
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
      command = "mcp-firecrawl";
      clients = [
        "claude"
      ];
    };

    lynchpin = {
      transport = "stdio";
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
      command = "mcp-polylogue";
      clients = [
        "codex"
        "claude"
        "gemini"
      ];
    };

    chrome-devtools = {
      transport = "stdio";
      command = "mcp-chrome-devtools";
      clients = [
        "claude"
        "codex"
        "gemini"
      ];
    };

    chrome-devtools-private = {
      transport = "stdio";
      command = "mcp-chrome-devtools-private";
      clients = [
        "claude"
        "codex"
        "gemini"
      ];
    };

    chrome-devtools-private-visible = {
      transport = "stdio";
      command = "mcp-chrome-devtools-private-visible";
      clients = [
        "claude"
        "codex"
        "gemini"
      ];
    };
  };

  selectClientServers =
    client: lib.filterAttrs (_: server: builtins.elem client server.clients) registry;

  # Claude Code mcpServers entry.
  renderClaudeServer =
    _name: server:
    pruneAttrs (
      if server.transport == "http" then
        {
          type = "http";
          url = server.url;
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
    selectClientServers
    renderClaudeServer
    renderCodexServer
    renderGeminiServer
    ;
}
