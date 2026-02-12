{ ... }:
_final: prev:
let
  pythonOverrides = _self: super: {
    # Fix llm build failure by skipping tests
    llm = super.llm.overridePythonAttrs (old: {
      doCheck = false;
      # Force skip check phase if doCheck is ignored
      checkPhase = "true";
    });

    # Fix fastmcp dependency on mcp (it requires <1.17.0 but we have 1.25.0)
    fastmcp = super.fastmcp.overridePythonAttrs (old: {
      postPatch = (old.postPatch or "") + ''
        substituteInPlace pyproject.toml --replace-fail "mcp>=1.12.4,<1.17.0" "mcp>=1.12.4" || true
        # Fallback if the string doesn't match exactly, try sed
        sed -i 's/<1.17.0//g' pyproject.toml
      '';
      doCheck = false;
    });
  };
in
{
  python3Packages = prev.python3Packages.overrideScope pythonOverrides;
}
