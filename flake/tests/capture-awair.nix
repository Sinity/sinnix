{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      lib = inputs.nixpkgs.lib;
      testLib = import ../test-lib.nix { inherit inputs lib; };
      evaluated = testLib.evalTestSpec system (
        testLib.mkServiceTest {
          name = "capture-awair";
          service = "capture-awair";
          assertions = _: [ ];
        }
      );
      command = evaluated.config.systemd.user.services.sinnix-capture-awair.serviceConfig.ExecStart;
    in
    {
      checks.capture-awair =
        pkgs.runCommand "capture-awair-check"
          {
            nativeBuildInputs = [ pkgs.python3 ];
            AWAIR_POLLER = builtins.head (lib.splitString " " command);
          }
          ''
            python3 ${./capture_awair.py}
            touch "$out"
          '';
    };
}
