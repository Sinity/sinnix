# Read-only operations reducer protocol and source-health fixture.
_: {
  perSystem =
    { sinnixScriptRegistry, ... }:
    {
      checks.ops-reducer = sinnixScriptRegistry.packageSet.sinnix-ops-reducer;
    };
}
