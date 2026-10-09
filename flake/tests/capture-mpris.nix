{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      lib = inputs.nixpkgs.lib;
      testLib = import ../test-lib.nix { inherit inputs lib; };
      privacy = testLib.evalTestSpec system {
        name = "capture-lane-privacy";
        modules = [
          testLib.mountTmpfsRoots
          testLib.baseTestConfig
          {
            sinnix.services.capture-kitty-scrollback.enable = true;
            sinnix.services.capture-mpris.enable = true;
            sinnix.services.capture-audio.enable = true;
            sinnix.services.capture-netflow.enable = true;
            sinnix.services.xiaomi-witness.enable = true;
          }
        ];
        assertions = config: [
          {
            assertion = config.systemd.user.services.sinnix-xiaomi-witness.serviceConfig.UMask == "0077";
            message = "Health witness writers must create owner-only output.";
          }
          {
            assertion = config.systemd.services.sinnix-capture-netflow.serviceConfig.UMask == "0077";
            message = "System capture writers must create owner-only output.";
          }
          {
            assertion =
              config.systemd.user.services.sinnix-capture-kitty-scrollback.serviceConfig.UMask == "0077";
            message = "Poll captures must create owner-only output.";
          }
          {
            assertion =
              config.home-manager.users.${config.sinnix.user.name}.systemd.user.services.sinnix-capture-mpris.Service.UMask
              == "0077";
            message = "Stream captures must create owner-only output.";
          }
          {
            assertion =
              builtins.all
                (
                  path:
                  builtins.elem "d ${path} 0700 ${config.sinnix.user.name} users -" config.systemd.tmpfiles.rules
                )
                [
                  config.sinnix.paths.capturePaths.kitty-scrollback
                  config.sinnix.paths.capturePaths.mpris
                  config.sinnix.paths.capturePaths.audio
                  config.sinnix.paths.capturePaths.audio-devices
                  config.sinnix.paths.capturePaths.audio-topology
                  config.sinnix.paths.capturePaths.audio-index
                  "${config.sinnix.paths.machineRoot}/netflow"
                  "/realm/health/xiaomi-cloud"
                ];
            message = "Private capture entrances must be owner-only.";
          }
        ];
      };
      sinnix-lib = pkgs.callPackage ../../pkgs/sinnix-lib/pkg.nix { };
      python = pkgs.python3.withPackages (_: [ sinnix-lib ]);
    in
    {
      # Exercise both factory routes through their real unit renderers.
      # Explicit lane overrides must not hide a regression in the defaults.
      checks.capture-lane-privacy =
        assert builtins.seq privacy true;
        pkgs.runCommand "capture-lane-privacy-check" { } ''touch "$out"'';
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
