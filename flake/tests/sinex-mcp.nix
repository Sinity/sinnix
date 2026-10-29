{
  perSystem =
    { sinnixScriptRegistry, ... }:
    {
      # Builds the provider-only backport and runs its native MCP unit tests.
      checks.sinex-mcp-provider = sinnixScriptRegistry.packageSet.sinex-mcp-cli;
    };
}
