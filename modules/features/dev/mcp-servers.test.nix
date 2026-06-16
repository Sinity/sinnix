{
  mkFeatureTest,
  expect,
  hmFor,
  inputs,
  ...
}:
mkFeatureTest {
  name = "dev-mcp-servers";
  feature = "sinnix.features.dev.mcp-servers.enable";
  assertions =
    config:
    let
      hm = hmFor config;
      managedEntryText =
        entry:
        if entry ? text && entry.text != null then
          entry.text
        else if entry ? source && entry.source != null then
          builtins.readFile entry.source
        else
          "";
      managedEntrySource =
        entry: if entry ? source && entry.source != null then toString entry.source else "";
      # config.toml is deployed via home.activation (writable file, not a Nix
      # store symlink). The module exposes the generated derivation path via
      # the internal codexConfigSource option for content assertions.
      codexConfigText = builtins.readFile config.sinnix.features.dev.mcp-servers.codexConfigSource;
      # Rendered Claude settings — merged from static base and registry mcpServers.
      # Compute inline rather than reading the rendered file because this test
      # exercises the dev.mcp-servers feature in isolation; agent-tools (which
      # owns the merge wiring) may not be enabled in the minimal config.
      mcpRegistry = import (inputs.self + "/flake/data/mcp-registry.nix") {
        lib = (inputs.nixpkgs.lib);
      };
      claudeSettings =
        let
          base = builtins.fromJSON (builtins.readFile (inputs.self + "/dots/claude/settings.json"));
          mcpServers = (inputs.nixpkgs.lib).mapAttrs mcpRegistry.renderClaudeServer (
            mcpRegistry.selectClientServers "claude"
          );
        in
        base // { inherit mcpServers; };
      geminiSettings = builtins.fromJSON (builtins.readFile hm.home.file.".gemini/settings.json".source);
      codexHooks = builtins.fromJSON (builtins.readFile hm.home.file.".codex/hooks.json".source);
    in
    [
      {
        assertion =
          builtins.match ".*zsh -lc.*" (
            builtins.readFile (
              inputs.self + "/dots/_ai/skills/agent-orchestration/scripts/launch_agent_tabs.sh"
            )
          ) == null;
        message = "Agent launcher must not wrap kitty launches in zsh -lc";
      }
      {
        assertion = hm.home.activation ? codexConfig;
        message = "Codex config must be deployed via home.activation (writable, not a Nix store symlink)";
      }
      {
        assertion = hm.home.activation ? codebaseMemoryMcpConfig;
        message = "Codebase Memory MCP defaults must be initialized during Home Manager activation";
      }
      {
        assertion = hm.home.activation ? serenaConfig;
        message = "Serena global config must be managed during Home Manager activation";
      }
      (expect.hmFileExists hm ".codex/skills"
        "Codex skills must be linked from the dedicated dots/codex/skills tree"
      )
      {
        assertion = !(hm.home.file.".codex/skills".recursive or false);
        message = "Codex skills must stay a direct directory symlink, not a recursive materialization";
      }
      (expect.textContains (managedEntrySource
        hm.home.file.".local/bin/mcp-firecrawl"
      ) "/bin/mcp-firecrawl" "Firecrawl wrapper must point at the packaged binary")
      (expect.textContains (managedEntryText hm.home.file.".local/bin/codebase-memory-mcp")
        ".local/share/codebase-memory-mcp"
        "Codebase Memory wrapper must keep graph state in persistent XDG data"
      )
      (expect.textContains (managedEntryText
        hm.home.file.".local/bin/codebase-memory-mcp"
      ) "/bin/codebase-memory-mcp" "Codebase Memory wrapper must launch the packaged binary")
      (expect.textContains (managedEntryText
        hm.home.file.".local/bin/serena"
      ) "serena-agent==1.5.3" "Serena wrapper must install the pinned upstream package version")
      (expect.textContains (managedEntryText
        hm.home.file.".local/bin/serena"
      ) ".local/share/serena" "Serena wrapper must keep user data in persistent XDG data")
      (expect.textContains (managedEntryText
        hm.home.file.".local/bin/serena-hooks"
      ) "serena-hooks" "Serena hooks wrapper must dispatch to the Serena hook command")
      (expect.persistedHomeDir config ".local/share/codebase-memory-mcp"
        "Codebase Memory graph store must persist across impermanence boots"
      )
      (expect.persistedHomeDir config ".local/share/serena"
        "Serena global configuration and logs must persist across impermanence boots"
      )
      (expect.persistedHomeDir config ".local/state/serena"
        "Serena uv tool installation must persist across impermanence boots"
      )
      (expect.textContains (managedEntrySource
        hm.home.file.".local/bin/mcp-playwright"
      ) "/bin/mcp-playwright" "Playwright wrapper must point at the packaged binary")
      (expect.textContains (managedEntryText
        hm.home.file.".local/bin/mcp-playwright"
      ) "/bin/playwright-mcp" "Playwright wrapper must launch the packaged server entrypoint")
      (expect.textContains (managedEntryText
        hm.home.file.".local/bin/mcp-polylogue"
      ) "/bin/polylogue-mcp" "Polylogue wrapper must launch the packaged MCP server entrypoint")
      (expect.textContains (managedEntryText hm.home.file.".local/bin/mcp-lynchpin")
        "export LYNCHPIN_REPO_ROOT=/realm/project/sinity-lynchpin"
        "Lynchpin wrapper must point runtime cache/config resolution at the writable project checkout"
      )
      (expect.textContains (managedEntryText hm.home.file.".local/bin/mcp-lynchpin")
        "export LYNCHPIN_LOCAL_ROOT=/realm/project/sinity-lynchpin/.lynchpin"
        "Lynchpin wrapper must keep generated substrate writes outside the Nix store"
      )
      (expect.textContains (managedEntryText hm.home.file.".local/bin/mcp-lynchpin")
        "export PYTHONPATH=\"$LYNCHPIN_REPO_ROOT"
        "Lynchpin wrapper must load MCP tool code from the writable project checkout"
      )
      (expect.textContains (managedEntryText hm.home.file.".local/bin/mcp-lynchpin")
        "lynchpin-python -m lynchpin.mcp.cli"
        "Lynchpin wrapper must run the packaged Python environment against the live MCP module"
      )
      (expect.textContains codexConfigText "[mcp_servers.polylogue]"
        "Codex config must declare the Polylogue MCP server"
      )
      (expect.textContains codexConfigText "command = \"mcp-polylogue\""
        "Codex config must call the packaged Polylogue MCP wrapper"
      )
      (expect.textContains codexConfigText "[mcp_servers.context7]"
        "Codex config must declare the Context7 MCP server"
      )
      (expect.textContains codexConfigText "url = \"https://mcp.context7.com/mcp\""
        "Codex config must point Context7 at the remote hosted endpoint"
      )
      (expect.textContains codexConfigText "bearer_token_env_var = \"CONTEXT7_API_KEY\""
        "Codex config must use bearer token auth for Context7"
      )
      (expect.textContains codexConfigText "[mcp_servers.github]"
        "Codex config must declare the GitHub MCP server"
      )
      (expect.textContains codexConfigText "bearer_token_env_var = \"GITHUB_TOKEN\""
        "Codex config must keep GitHub token lookup in the environment"
      )
      (expect.textContains codexConfigText "[mcp_servers.codebase-memory-mcp]"
        "Codex config must declare the Codebase Memory MCP server"
      )
      (expect.textContains codexConfigText "command = \"codebase-memory-mcp\""
        "Codex config must call the managed Codebase Memory wrapper"
      )
      (expect.textContains codexConfigText "[mcp_servers.serena]"
        "Codex config must declare the Serena MCP server"
      )
      (expect.textContains codexConfigText "startup_timeout_sec = 15"
        "Codex Serena config must allow enough startup time for language-server initialization"
      )
      (expect.textContains codexConfigText
        "args = [\"start-mcp-server\", \"--project-from-cwd\", \"--context=codex\"]"
        "Codex Serena config must use the Codex context and activate from the working directory"
      )
      (expect.attrPathEq claudeSettings [
        "mcpServers"
        "codebase-memory-mcp"
        "command"
      ] "codebase-memory-mcp" "Claude config must call the managed Codebase Memory wrapper")
      (expect.attrPathEq claudeSettings [
        "mcpServers"
        "serena"
        "command"
      ] "serena" "Claude config must call the managed Serena wrapper")
      (expect.attrPathEq claudeSettings
        [
          "mcpServers"
          "serena"
          "args"
        ]
        [
          "start-mcp-server"
          "--project-from-cwd"
          "--context=claude-code"
        ]
        "Claude Serena config must use the Claude Code context and activate from the working directory"
      )
      (expect.attrPathEq claudeSettings [
        "mcpServers"
        "polylogue"
        "command"
      ] "mcp-polylogue" "Claude config must call the packaged Polylogue MCP wrapper")
      (expect.attrPathEq claudeSettings [
        "mcpServers"
        "lynchpin"
        "env"
        "LYNCHPIN_REPO_ROOT"
      ] "/realm/project/sinity-lynchpin" "Claude config must pass the writable Lynchpin repo root")
      (expect.attrPathEq claudeSettings
        [
          "mcpServers"
          "lynchpin"
          "env"
          "LYNCHPIN_LOCAL_ROOT"
        ]
        "/realm/project/sinity-lynchpin/.lynchpin"
        "Claude config must pass the writable Lynchpin local root"
      )
      (expect.attrPathEq geminiSettings [
        "mcpServers"
        "codebase-memory-mcp"
        "command"
      ] "codebase-memory-mcp" "Gemini config must call the managed Codebase Memory wrapper")
      (expect.attrPathEq geminiSettings
        [
          "mcpServers"
          "serena"
          "args"
        ]
        [
          "start-mcp-server"
          "--project-from-cwd"
          "--context=ide"
        ]
        "Gemini Serena config must use the generic IDE context and activate from the working directory"
      )
      (expect.attrPathEq geminiSettings [
        "mcpServers"
        "polylogue"
        "command"
      ] "mcp-polylogue" "Gemini config must call the packaged Polylogue MCP wrapper")
      {
        assertion =
          (builtins.elemAt (builtins.elemAt codexHooks.hooks.SessionStart 0).hooks 0).command
          == "serena-hooks activate --client=codex";
        message = "Codex hooks must activate Serena at session start";
      }
      {
        assertion = !(hm.home.file.".gemini/skills".recursive or false);
        message = "Gemini skills must stay a direct directory symlink, not a recursive materialization";
      }
      (expect.attrPathEq geminiSettings [
        "mcpServers"
        "context7"
        "httpUrl"
      ] "https://mcp.context7.com/mcp" "Gemini config must point Context7 at the remote hosted endpoint")
      (expect.attrPathEq geminiSettings [
        "mcpServers"
        "github"
        "httpUrl"
      ] "https://api.githubcopilot.com/mcp/" "Gemini config must keep the GitHub MCP endpoint")
      (expect.attrPathEq geminiSettings [
        "mcpServers"
        "github"
        "headers"
        "Authorization"
      ] "Bearer \${GITHUB_TOKEN}" "Gemini config must keep GitHub auth as runtime header expansion")
      (expect.attrPathEq geminiSettings [
        "general"
        "enableAutoUpdate"
      ] false "Gemini must keep self-update disabled")
      (expect.attrPathEq geminiSettings [
        "general"
        "enableAutoUpdateNotification"
      ] false "Gemini must keep update notifications disabled")
      (expect.attrPathEq geminiSettings [
        "general"
        "checkpointing"
        "enabled"
      ] true "Gemini must retain checkpointing")
      (expect.attrPathEq geminiSettings [
        "general"
        "sessionRetention"
        "maxCount"
      ] 1000000 "Gemini must keep the long session-retention budget")
      (expect.attrPathEq geminiSettings [
        "model"
        "maxSessionTurns"
      ] (-1) "Gemini must keep unlimited session turns")
    ];
}
