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
        "forge"
        "hermes"
      ];
      hermes.headers.Authorization = "Bearer \${CONTEXT7_API_KEY}";
    };

    github = {
      transport = "http";
      url = "https://api.githubcopilot.com/mcp/";
      clients = [
        "codex"
        "gemini"
        "hermes"
      ];
      codex.bearer_token_env_var = "GITHUB_TOKEN";
      gemini.headers.Authorization = "Bearer \${GITHUB_TOKEN}";
      hermes.headers.Authorization = "Bearer \${GITHUB_TOKEN}";
    };

    firecrawl = {
      transport = "stdio";
      command = "mcp-firecrawl";
      clients = [
        "forge"
        "hermes"
      ];
    };

    polylogue = {
      transport = "stdio";
      command = "mcp-polylogue";
      clients = [
        "codex"
        "claude"
        "gemini"
        "forge"
        "hermes"
      ];
    };

    playwright = {
      transport = "stdio";
      command = "mcp-playwright";
      args = [ "--headless" ];
      clients = [
        "forge"
        "hermes"
      ];
    };
  };

  selectClientServers =
    client: lib.filterAttrs (_: server: builtins.elem client server.clients) registry;

  renderForgeServer =
    _name: server:
    pruneAttrs (
      if server.transport == "http" then
        {
          url = server.url;
          disable = false;
        }
      else
        {
          inherit (server) command;
          args = server.args or [ ];
          disable = false;
        }
    );

  renderHermesServer =
    _name: server:
    let
      client = server.hermes or { };
      common = {
        timeout = server.timeout or client.timeout or null;
        connect_timeout = server.connect_timeout or client.connect_timeout or null;
        enabled = server.enabled or client.enabled or true;
        tools = server.tools or client.tools or null;
      };
    in
    pruneAttrs (
      common
      // (
        if server.transport == "http" then
          {
            url = server.url;
            headers = client.headers or server.headers or { };
            auth = client.auth or server.auth or null;
          }
        else
          {
            inherit (server) command;
            args = server.args or [ ];
            env = client.env or server.env or { };
          }
      )
    );
in
{
  inherit
    registry
    selectClientServers
    renderForgeServer
    renderHermesServer
    ;
}
