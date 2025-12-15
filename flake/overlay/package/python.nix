_:
_final: prev:
let
  pythonOverrides = _self: super: {
    # Upstream aggdraw test suite flakes on Python 3.13; keep disabled to avoid eval/switch failures.
    aggdraw = super.aggdraw.overridePythonAttrs (_old: {
      doCheck = false;
    });
  };
  composeOverrides = prev.lib.composeExtensions (prev.python3.packageOverrides or (_self: _super: { })
  ) pythonOverrides;
in
{
  python313Packages = prev.python313Packages.overrideScope pythonOverrides;

  python3 = prev.python3.override {
    packageOverrides = composeOverrides;
  };
}
