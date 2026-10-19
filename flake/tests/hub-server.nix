# Read-only hub server protocol and source-health fixture.
_: {
  perSystem =
    { sinnixScriptRegistry, ... }:
    {
      checks.hub-server = sinnixScriptRegistry.packageSet.sinnix-hub-server;
    };
}
