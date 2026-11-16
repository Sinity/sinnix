{ lib }:
let
  pruneAttrs = lib.filterAttrs (_: value: value != null && value != [ ] && value != { });
  readActions =
    tool: actions:
    map (action: {
      inherit tool;
      arguments = { inherit action; };
    }) actions;

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
        "hermes"
      ];
      codex.bearer_token_env_var = "CONTEXT7_API_KEY";
      hermes.headers.Authorization = "Bearer \${CONTEXT7_API_KEY}";
    };

    github = {
      description = "GitHub issues, pull requests, and repository operations";
      transport = "stdio";
      tier = "remote-core";
      command = "mcp-github";
      env = {
        GITHUB_PERSONAL_ACCESS_TOKEN = "\${GITHUB_TOKEN}";
      };
      clients = [
        "claude"
        "codex"
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
      callTimeoutSeconds = 300;
      command = "mcp-lynchpin";
      # Mixed routers stay change at the tool grain. These action contracts are
      # documented reads and are admitted through mcp.call without mcp.change.
      gatewayReadOnlyRoutes =
        readActions "lynchpin_project" [
          "campaign_evidence"
          "campaign_progress"
          "campaign_scope_delta"
          "verification_regression"
          "project_trajectory"
          "project_context"
          "repos"
          "files"
          "commits"
          "github"
        ]
        ++ readActions "lynchpin_evidence" [
          "coverage"
          "confidence"
        ]
        ++ readActions "lynchpin_personal" [
          "phone"
          "health"
          "media"
          "reports"
        ]
        ++ readActions "lynchpin_machine" [
          "status"
          "workloads"
          "benchmarks"
          "diagnostics"
        ]
        ++ readActions "lynchpin_ops" [ "receipt" ];
      clients = [
        "codex"
        "claude"
        "hermes"
      ];
    };

    polylogue = {
      description = "AI chat archive: search and read past Claude, Codex, and ChatGPT sessions";
      transport = "stdio";
      tier = "recall";
      command = "mcp-polylogue";
      # Let the daemon's default 30s read deadline return its typed refusal.
      callTimeoutSeconds = 35;
      profiles = {
        evidence = { };
        browser = { };
        default = { };
      };
      clients = [
        "codex"
        "claude"
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
        "hermes"
      ];
    };
  };

  profileTiers = {
    default = [
      "remote-core"
      "recall"
    ];
    evidence = [
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
    selectClientServersForProfile
    renderClaudeServer
    renderCodexServer
    renderHermesServer
    ;
}
