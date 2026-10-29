# IOCost and IOLatency use incompatible blkcg delay modes. The workstation
# initializer enables IOCost on every physical device, so a path alias cannot
# give an independent latency target a different controller owner.
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      testLib = import ../test-lib.nix { inherit inputs lib; };
      evaluated = testLib.evalTestSpec system (
        testLib.mkFeatureTest {
          name = "block-io-controller";
          feature = "sinnix.machine.isDesktop";
          assertions =
            config:
            let
              costEnabled = config.systemd.services.sinnix-iocost-init.enable;
              policies =
                (map (unit: unit.sliceConfig) (lib.attrValues config.systemd.slices))
                ++ (map (unit: unit.sliceConfig) (lib.attrValues config.systemd.user.slices))
                ++ (map (unit: unit.serviceConfig) (lib.attrValues config.systemd.services))
                ++ (map (unit: unit.serviceConfig) (lib.attrValues config.systemd.user.services));
              hasLatencyTarget =
                policy:
                lib.any (target: target != null && target != "") (
                  lib.toList (policy.IODeviceLatencyTargetSec or [ ])
                );
            in
            [
              {
                assertion = costEnabled;
                message = "The desktop must retain its all-device IOCost owner";
              }
              {
                assertion = !costEnabled || !(lib.any hasLatencyTarget policies);
                message = "All-device IOCost cannot share a device with IOLatency, including targets expressed through path aliases";
              }
            ];
        }
      );
    in
    {
      checks.block-io-controller =
        assert evaluated.config.sinnix.machine.isDesktop;
        pkgs.runCommand "block-io-controller-check" { } ''
          touch "$out"
        '';
    };
}
