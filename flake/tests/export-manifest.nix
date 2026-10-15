{ ... }:
{
  perSystem =
    { pkgs, sinnixScriptRegistry, ... }:
    {
      checks.export-manifest =
        pkgs.runCommand "export-manifest-check"
          {
            nativeBuildInputs = [ pkgs.python3 ];
          }
          ''
            export EXPORT_MANIFEST=${sinnixScriptRegistry.packageSet.sinnix-export-manifest}/bin/sinnix-export-manifest
            python3 ${./export_manifest.py}
            export EXPORT_MANIFEST_SOURCE=${../../scripts/sinnix-export-manifest}
            PYTHONPATH=${sinnixScriptRegistry.packageSet.sinnix-lib}/${pkgs.python3.sitePackages} python3 ${./export_manifest_races.py}
            touch "$out"
          '';
    };
}
