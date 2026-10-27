# Check the rendered policy at both hierarchy levels and on both SSDs.
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
            in
            map (policy: {
              assertion =
                policy.IOAccounting
                && builtins.all (target: builtins.elem target policy.IODeviceLatencyTargetSec) [
                  "/nix 20ms"
                  "/realm 20ms"
                ];
              message = "Interactive disk latency protection must reach both SSDs, the shell, and root peer slices including the input ancestor";
            }) protected;
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
