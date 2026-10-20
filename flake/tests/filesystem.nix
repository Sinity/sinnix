{ ... }:
{
  perSystem = { pkgs, sinnixScriptRegistry, ... }: {
    checks.filesystem-suite =
      pkgs.runCommand "sinnix-filesystem-suite"
        {
          nativeBuildInputs = [
            (pkgs.python3.withPackages (ps: [
              ps.pytest
              sinnixScriptRegistry.packageSet.sinnix-fs
            ]))
            pkgs.nodejs
            pkgs.duckdb
            pkgs.file
            pkgs.ripgrep
            pkgs.util-linux
            pkgs.btrfs-progs
          ];
          SINNIX_FS_EXECUTABLE = "${sinnixScriptRegistry.packageSet.sinnix-fs}/bin/sinnix-fs";
        }
        ''
          cp -r ${../../pkgs/sinnix-fs/tests} tests
          chmod -R u+w tests
          python3 -m pytest -q tests
          touch "$out"
        '';
  };
}
