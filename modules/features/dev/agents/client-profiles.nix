# Registry-driven MCP config generation for the default Codex configuration
# and its alternate backends. Imported by mcp.nix.
{
  lib,
  pkgs,
  inputs,
  mcpRegistry,
  tomlFormat,
  dotsRoot,
  agentProfiles,
}:
let
  inherit (mcpRegistry)
    selectClientServersForProfile
    renderCodexServer
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
    lib.mapAttrsToList (_: profile: profile.mcpProfile) (
      lib.filterAttrs (_: profile: profile ? env) agentProfiles.codexProfiles
    )
  );
  codexEndpointFiles = lib.genAttrs codexEndpointProfileNames (
    name: mkCodexBackendProfileFile name mcpRegistry.codexEndpoints.${name}
  );
in
{
  inherit
    codexSystemConfigFile
    codexEndpointFiles
    ;
}
