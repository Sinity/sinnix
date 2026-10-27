# Check desktop latency protection and the aggregate agent device limits.
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
          name = "desktop-io";
          feature = "sinnix.machine.isDesktop";
          assertions =
            config:
            let
              protected =
                (map (name: config.systemd.slices.${name}.sliceConfig) [
                  "system"
                  "user"
                  "system-critical"
                ])
                ++ (map (name: config.systemd.user.slices.${name}.sliceConfig) [
                  "app"
                  "session"
                  "desktop"
                  "desktop-shell"
                ]);
              agentUnit = config.systemd.user.units."agent.slice".text;
            in
            (map (policy: {
              assertion =
                policy.IOAccounting
                && builtins.all (target: builtins.elem target policy.IODeviceLatencyTargetSec) [
                  "/nix 20ms"
                  "/realm 20ms"
                ];
              message = "Interactive disk latency protection must reach both SSDs, the shell, and root peer slices including the input ancestor";
            }) protected)
            ++ [
              {
                assertion = builtins.all (line: lib.hasInfix line agentUnit) [
                  "IOAccounting=true"
                  "IOReadBandwidthMax=/realm 32M"
                  "IOReadIOPSMax=/realm 500"
                  "IOWriteBandwidthMax=/realm 4M"
                  "IOWriteIOPSMax=/realm 200"
                ];
                message = "The rendered agent parent must cap aggregate Realm reads and writes across CLI, tool and job slices";
              }
            ];
        }
      );
    in
    {
      checks.desktop-io =
        assert evaluated.config.sinnix.machine.isDesktop;
        pkgs.runCommand "desktop-io-check" { } ''
          touch "$out"
        '';
    };
}
