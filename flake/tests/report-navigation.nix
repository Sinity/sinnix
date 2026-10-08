{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
    in
    {
      checks.report-navigation-suite =
        pkgs.runCommand "report-navigation-suite"
          {
            nativeBuildInputs = [ (pkgs.python3.withPackages (ps: [ ps.pytest ])) ];
          }
          ''
            mkdir -p generators tests
            cp ${../../dots/_ai/skills/html-report/generators/reports-index.py} generators/reports-index.py
            cp ${../../dots/_ai/skills/html-report/tests/test_reports_index.py} tests/test_reports_index.py
            python3 -m pytest -q tests/test_reports_index.py
            touch "$out"
          '';
    };
}
