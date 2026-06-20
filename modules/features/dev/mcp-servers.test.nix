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
        assertion = hm.home.activation ? codexConfig;
        message = "Codex config must be deployed via home.activation (writable, not a Nix store symlink)";
      }
      {
        assertion = hm.home.activation ? codebaseMemoryMcpConfig;
        message = "Codebase Memory MCP defaults must be initialized during Home Manager activation";
      }
      {
        assertion = hm.systemd.user.services ? codebase-memory-ui;
        message = "Codebase Memory Web UI must be managed as a user service";
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
      (expect.persistedHomeDir config ".local/share/codebase-memory-mcp"
        "Codebase Memory graph store must persist across impermanence boots"
      )
      (expect.persistedHomeDir config ".local/share/serena"
        "Serena global configuration and logs must persist across impermanence boots"
      )
      (expect.persistedHomeDir config ".local/state/serena"
        "Serena uv tool installation must persist across impermanence boots"
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
        "chrome-devtools"
        "command"
      ] "mcp-chrome-devtools" "Claude config must expose the user's Chrome DevTools MCP")
      (expect.attrPathEq claudeSettings [
        "mcpServers"
        "chrome-devtools-private"
        "command"
      ] "mcp-chrome-devtools-private" "Claude config must expose the private Chrome DevTools MCP")
      (expect.attrPathEq claudeSettings
        [
          "mcpServers"
          "chrome-devtools-private-visible"
          "command"
        ]
        "mcp-chrome-devtools-private-visible"
        "Claude config must expose the visible private Chrome DevTools MCP"
      )
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
      (expect.attrPathEq geminiSettings [
        "mcpServers"
        "chrome-devtools"
        "command"
      ] "mcp-chrome-devtools" "Gemini config must expose the user's Chrome DevTools MCP")
      (expect.attrPathEq geminiSettings [
        "mcpServers"
        "chrome-devtools-private"
        "command"
      ] "mcp-chrome-devtools-private" "Gemini config must expose the private Chrome DevTools MCP")
      (expect.attrPathEq geminiSettings
        [
          "mcpServers"
          "chrome-devtools-private-visible"
          "command"
        ]
        "mcp-chrome-devtools-private-visible"
        "Gemini config must expose the visible private Chrome DevTools MCP"
      )
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
      (expect.hmFileExists hm ".local/bin/sinnix-chrome-control"
        "Agent Chrome CDP helper must be available on PATH"
      )
      (expect.hmFileExists hm ".local/bin/sinnix-hypr-control"
        "Agent Hyprland helper must be available on PATH"
      )
      (expect.hmFileExists hm ".local/bin/sinnix-keyboard-control"
        "Agent keyboard helper must be available on PATH"
      )
      (expect.hmFileExists hm ".local/bin/sinnix-kitty-control"
        "Agent Kitty helper must be available on PATH"
      )
      (expect.hmFileExists hm ".local/bin/sinnix-screenshot-control"
        "Agent screenshot helper must be available on PATH"
      )
      (expect.hmFileExists hm ".local/bin/sinnix-agent-control-status"
        "Agent control surface probe must be available on PATH"
      )
    ];
}
