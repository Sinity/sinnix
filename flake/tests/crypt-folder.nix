{ ... }:
{
  perSystem = { pkgs, sinnixScriptRegistry, ... }: {
    checks.crypt-folder =
      pkgs.runCommand "crypt-folder-check"
        {
          nativeBuildInputs = [
            pkgs.python3
            pkgs.bash
          ];
          CRYPT_FOLDER = "${sinnixScriptRegistry.packageSet.crypt-folder}/bin/crypt-folder";
        }
        ''
          python3 ${./crypt_folder.py}
          touch "$out"
        '';
  };
}
