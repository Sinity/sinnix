{ mkFeatureTest, expect, hmFor, inputs, ... }:
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
      codexConfigText = builtins.readFile (inputs.self + "/dots/codex/config.toml");
      claudeSettings = builtins.fromJSON (builtins.readFile (inputs.self + "/dots/claude/settings.json"));
      geminiSettings = builtins.fromJSON (builtins.readFile (inputs.self + "/dots/gemini/settings.json"));
      forgeMcpConfig = builtins.fromJSON (managedEntryText hm.home.file."forge/.mcp.json");
    in
    [
      {
        assertion =
          builtins.match ".*zsh -lc.*" (
            builtins.readFile (inputs.self + "/dots/_ai/skills/agent-orchestration/scripts/launch_agent_tabs.sh")
          ) == null;
        message = "Agent launcher must not wrap kitty launches in zsh -lc";
      }
      (expect.hmFileExists hm ".codex/config.toml" "Codex config must be managed")
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
      (expect.textContains (managedEntrySource
        hm.home.file.".local/bin/mcp-playwright"
      ) "/bin/mcp-playwright" "Playwright wrapper must point at the packaged binary")
      (expect.textContains (managedEntryText
        hm.home.file.".local/bin/mcp-playwright"
      ) "/bin/mcp-server-playwright" "Playwright wrapper must launch the packaged server entrypoint")
      (expect.textContains (managedEntrySource
        hm.home.file.".local/bin/mcp-polylogue"
      ) "/bin/mcp-polylogue" "Polylogue wrapper must point at the packaged binary")
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
      (expect.attrPathEq claudeSettings [
        "mcpServers"
        "polylogue"
        "command"
      ] "mcp-polylogue" "Claude config must call the packaged Polylogue MCP wrapper")
      (expect.attrPathEq geminiSettings [
        "mcpServers"
        "polylogue"
        "command"
      ] "mcp-polylogue" "Gemini config must call the packaged Polylogue MCP wrapper")
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
      (expect.attrPathEq forgeMcpConfig
        [
          "mcpServers"
          "context7"
          "url"
        ]
        "https://mcp.context7.com/mcp"
        "Forge MCP config must point Context7 at the remote hosted endpoint"
      )
      (expect.attrPathEq forgeMcpConfig [
        "mcpServers"
        "firecrawl"
        "command"
      ] "mcp-firecrawl" "Forge MCP config must call the packaged Firecrawl wrapper")
      (expect.attrPathEq forgeMcpConfig [
        "mcpServers"
        "playwright"
        "command"
      ] "mcp-playwright" "Forge MCP config must call the packaged Playwright wrapper")
      (expect.attrPathEq forgeMcpConfig [ "mcpServers" "playwright" "args" ] [ "--headless" ]
        "Forge MCP config must keep Playwright headless by default"
      )
      (expect.attrPathEq forgeMcpConfig [
        "mcpServers"
        "polylogue"
        "command"
      ] "mcp-polylogue" "Forge MCP config must call the packaged Polylogue wrapper")
    ];
}
