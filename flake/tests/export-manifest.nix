{ ... }:
{
  perSystem =
    { pkgs, sinnixScriptRegistry, ... }:
    {
      checks.export-manifest =
        pkgs.runCommand "export-manifest-check" { nativeBuildInputs = [ pkgs.python3 ]; }
          ''
            export EXPORT_MANIFEST=${sinnixScriptRegistry.packageSet.sinnix-export-manifest}/bin/sinnix-export-manifest
            python3 ${./export_manifest.py}
            touch "$out"
          '';
    };
}
