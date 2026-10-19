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
          name = "capture-idle-inhibitors";
          service = "capture-idle-inhibitors";
          assertions = config: [
            {
              assertion =
                map (
                  row:
                  lib.getAttrs [
                    "name"
                    "path"
                    "cadenceSeconds"
                    "staleAfterSeconds"
                    "eventDriven"
                    "requiredPayloadFields"
                  ] row
                ) config.sinnix.runtime.units.capture-idle-inhibitors.captures == [
                  {
                    name = "idle-inhibitors";
                    path = config.sinnix.paths.capturePaths.idle-inhibitors;
                    cadenceSeconds = 300;
                    staleAfterSeconds = 900;
                    eventDriven = true;
                    requiredPayloadFields = [
                      "event"
                      "provenance"
                    ];
                  }
                ];
              message = "Inhibitor capture registration must retain its provenance and heartbeat contract.";
            }
          ];
        }
      );
      command =
        evaluated.config.home-manager.users.${evaluated.config.sinnix.user.name}.systemd.user.services.sinnix-capture-idle-inhibitors.Service.ExecStart;
    in
    {
      checks.capture-idle-inhibitors =
        pkgs.runCommand "capture-idle-inhibitors-check"
          {
            nativeBuildInputs = [ pkgs.python3 ];
            UNIT_COMMAND = command;
          }
          ''
            python3 ${./capture_idle_inhibitors.py}
            touch "$out"
          '';
    };
}
