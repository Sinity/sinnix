{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      sinnix-lib = pkgs.callPackage ../../pkgs/sinnix-lib/pkg.nix { };
    in
    {
      checks.file-catalog-suite =
        pkgs.runCommand "sinnix-file-catalog-suite-check"
          {
            nativeBuildInputs = [
              # The page-script test runs the report's filter under Node.
              pkgs.nodejs
              (pkgs.python3.withPackages (ps: [
                ps.pytest
                sinnix-lib
              ]))
            ];
          }
          ''
            mkdir -p scripts pkgs/sinnix-file-catalog/tests
            cp ${../../scripts/sinnix-file-catalog} scripts/sinnix-file-catalog
            cp ${../../scripts/sinnix-file-catalog-report} scripts/sinnix-file-catalog-report
            cp ${../../scripts/sinnix-report-site} scripts/sinnix-report-site
            chmod +x scripts/*
            patchShebangs scripts
            cp ${../../pkgs/sinnix-file-catalog/tests}/*.py pkgs/sinnix-file-catalog/tests/
            python3 -m pytest -q pkgs/sinnix-file-catalog/tests
            touch "$out"
          '';
    };
}
