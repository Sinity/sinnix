# Registry-driven per-client MCP config generation: Codex full/lean/
# evidence/browser profiles plus the alternate-backend (deepseek/local)
# profiles and the Gemini settings.json MCP table. Plain helper — imported by mcp.nix's
# configFn, not picked up by auto-import.
{
  lib,
  pkgs,
  inputs,
  mcpRegistry,
  tomlFormat,
  jsonFormat,
  dotsRoot,
  agentLanes,
}:
let
  inherit (mcpRegistry)
    selectClientServersForProfile
    renderCodexServer
    renderGeminiServer
    renderAntigravityServer
    ;
  mkCodexProfileFile =
    profile:
    tomlFormat.generate "codex-${profile}-profile.toml" {
      mcp_servers = lib.mapAttrs renderCodexServer (selectClientServersForProfile profile "codex");
    };
  codexProfileFiles = lib.genAttrs mcpRegistry.codexProfileNames mkCodexProfileFile;
  # Alternate-backend profiles: the full MCP table plus a model + provider.
  # `codex --profile <name>` layers these over ~/.codex/config.toml, so the
  # provider's base_url/env_key and the chosen model override the gpt-5.6-luna
  # defaults while keeping the full MCP surface.
  mkCodexBackendProfileFile =
    name: extra:
    tomlFormat.generate "codex-${name}-profile.toml" (
      {
        mcp_servers = lib.mapAttrs renderCodexServer (selectClientServersForProfile "full" "codex");
      }
      // extra
    );
  codexEndpointProfileNames = lib.unique (
    lib.mapAttrsToList (_: lane: lane.mcpProfile) (
      lib.filterAttrs (
        _: lane: lane ? env && !(builtins.elem lane.mcpProfile mcpRegistry.codexProfileNames)
      ) agentLanes.codexLanes
    )
  );
  codexEndpointFiles = lib.genAttrs codexEndpointProfileNames (
    name: mkCodexBackendProfileFile name mcpRegistry.codexEndpoints.${name}
  );
  geminiSettingsBase = removeAttrs (builtins.fromJSON (
    builtins.readFile (inputs.self + "/dots/gemini/settings.json")
  )) [ "mcpServers" ];
  geminiSettingsFile = jsonFormat.generate "gemini-settings.json" (
    geminiSettingsBase
    // {
      mcpServers = lib.mapAttrs renderGeminiServer (selectClientServersForProfile "full" "gemini");
    }
  );
  antigravityMcpConfigFile = jsonFormat.generate "antigravity-mcp-config.json" {
    mcpServers = lib.mapAttrs renderAntigravityServer (
      selectClientServersForProfile "antigravity" "antigravity"
    );
  };
in
{
  inherit
    codexProfileFiles
    codexEndpointFiles
    geminiSettingsFile
    antigravityMcpConfigFile
    ;
}
