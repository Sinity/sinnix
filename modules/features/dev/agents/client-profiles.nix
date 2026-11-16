# Registry-driven MCP table for the generated Codex system configuration.
# Imported by mcp.nix.
{
  lib,
  inputs,
  mcpRegistry,
  tomlFormat,
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
in
{
  inherit
    codexSystemConfigFile
    ;
}
