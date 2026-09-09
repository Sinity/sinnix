{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
    in
    {
      checks.file-catalog-suite =
        pkgs.runCommand "sinnix-file-catalog-suite-check"
          {
            nativeBuildInputs = [ (pkgs.python3.withPackages (ps: [ ps.pytest ])) ];
          }
          ''
            mkdir -p scripts pkgs/sinnix-file-catalog/tests
            cp ${../../scripts/sinnix-file-catalog} scripts/sinnix-file-catalog
            cp ${../../scripts/sinnix-file-catalog-report} scripts/sinnix-file-catalog-report
            chmod +x scripts/*
            patchShebangs scripts
            cp ${../../pkgs/sinnix-file-catalog/tests}/*.py pkgs/sinnix-file-catalog/tests/
            python3 -m pytest -q pkgs/sinnix-file-catalog/tests
            touch "$out"
          '';
    };
}
