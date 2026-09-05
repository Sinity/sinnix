# Provider quota normalization, redaction, and disagreement fixture.
_: {
  perSystem =
    { sinnixScriptRegistry, ... }:
    {
      checks = {
        quota = sinnixScriptRegistry.packageSet.sinnix-quota;
        codexbar = sinnixScriptRegistry.packageSet.sinnix-quota.passthru.codexbar;
      };
    };
}
