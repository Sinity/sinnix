# Check the rendered IOCost hierarchy without inventing a hard latency promise.
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
            (map (policy: {
              assertion = policy.IOAccounting;
              message = "Interactive I/O accounting must reach the shell and root peer slices";
            }) protected)
            ++ [
              {
                assertion = config.systemd.slices.user.sliceConfig.IOWeight == 400;
                message = "The root user slice must retain its foreground IOCost weight";
              }
              {
                assertion = lib.all (policy: policy.IOWeight == 300) (lib.drop 2 protected);
                message = "Critical services and desktop routes must retain their IOCost weights";
              }
              {
                assertion =
                  config.systemd.user.slices.agent.sliceConfig.IOWeight == 25
                  && config.systemd.user.slices.agent-tool.sliceConfig.IOWeight == 90
                  && config.systemd.user.slices.agent-ctl.sliceConfig.IOWeight == 100;
                message = "The agent hierarchy must retain its existing relative I/O weights";
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
