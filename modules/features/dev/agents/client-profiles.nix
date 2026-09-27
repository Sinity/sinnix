# Registry-driven MCP config generation for the default Codex configuration,
# its alternate backends, and Gemini/Antigravity. Imported by mcp.nix.
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
  codexSystemConfigFile = tomlFormat.generate "codex-system-config.toml" (
    builtins.fromTOML (builtins.readFile (inputs.self + "/dots/codex/config.toml"))
    // {
      mcp_servers = lib.mapAttrs renderCodexServer (selectClientServersForProfile "default" "codex");
    }
  );
  # Alternate-backend profiles: the full MCP table plus a model + provider.
  # `codex --profile <name>` layers these over ~/.codex/config.toml, so the
  # provider's base_url/env_key and the chosen model override the gpt-6-luna
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
      lib.filterAttrs (_: lane: lane ? env) agentLanes.codexLanes
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
    codexSystemConfigFile
    codexEndpointFiles
    geminiSettingsFile
    antigravityMcpConfigFile
    ;
}
