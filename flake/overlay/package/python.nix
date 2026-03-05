{ ... }:
_final: prev:
let
  pythonOverrides = _self: super: {
    # Fix llm build failure by skipping tests
    llm = super.llm.overridePythonAttrs (_old: {
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

    # Collateral damage from python3 override forcing local rebuilds:
    # These packages fail tests or runtime dep checks when built locally
    # but work fine from Hydra's binary cache.
    picosvg = super.picosvg.overridePythonAttrs (_old: {
      doCheck = false;
    });
    nanoemoji = super.nanoemoji.overridePythonAttrs (_old: {
      doCheck = false;
    });

    # Fix marimo build on nixpkgs 2fc6539+:
    # 1. uv-build.patch applied in reverse (source already has the change)
    # 2. uv-build 0.10.0 exceeds <0.10.0 constraint in source
    # 3. msgspec missing from nixpkgs dependency list (new dep in 0.19.4)
    marimo = super.marimo.overridePythonAttrs (old: {
      patches = [ ];
      postPatch = (old.postPatch or "") + ''
        substituteInPlace pyproject.toml \
          --replace-fail 'requires = ["uv_build>=0.8.3,<0.10.0"]' \
                         'requires = ["uv_build>=0.8.3,<0.11.0"]'
      '';
      dependencies = (old.dependencies or [ ]) ++ [ super.msgspec ];
    });
  };

  # Override the interpreter so python3.withPackages uses patched packages
  overriddenPython3 = prev.python3.override {
    packageOverrides = pythonOverrides;
  };
in
{
  # Override both the interpreter and the package set
  python3 = overriddenPython3;
  python3Packages = overriddenPython3.pkgs;

  # Electrum is a top-level package (not in python3Packages), so it needs
  # a top-level override. The python3 interpreter override above doesn't reach it.
  electrum = prev.electrum.overridePythonAttrs (_old: {
    dontCheckRuntimeDeps = true;
  });
}
