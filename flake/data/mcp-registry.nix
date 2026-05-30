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

    playwright = {
      transport = "stdio";
      command = "mcp-playwright";
      # Headless is the safe default for autonomous agents; per-client overrides
      # can swap to the headed variant when interacting with the user's session.
      args = [ "--headless" ];
      clients = [
        "claude"
        "codex"
        "gemini"
      ];
    };

    # Headed Playwright variant against a persistent dev profile. Use when an
    # extension or auth-required UI must be exercised against a real browser
    # session. The wrapper resolves to `mcp-playwright-headed`.
    playwright-headed = {
      transport = "stdio";
      command = "mcp-playwright-headed";
      clients = [
        "claude"
        "codex"
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
        {
          inherit (server) command;
          args = server.args or [ ];
          env = server.env or { };
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
        {
          inherit (server) command;
          args = server.args or [ ];
          env = server.env or { };
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
        {
          inherit (server) command;
          args = server.args or [ ];
          env = server.env or { };
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
