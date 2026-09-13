{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      sinnix-lib = pkgs.callPackage ../../pkgs/sinnix-lib/pkg.nix { };
      python = pkgs.python3.withPackages (_: [ sinnix-lib ]);
    in
    {
      checks.capture-mpris =
        pkgs.runCommand "capture-mpris-check"
          {
            nativeBuildInputs = [ python ];
          }
          ''
            python3 -m unittest discover -v \
              -s ${../../pkgs/capture-mpris} -p 'test_monitor.py'
            touch "$out"
          '';
    };
}
