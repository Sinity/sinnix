{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      lib = inputs.nixpkgs.lib;
      testLib = import ../test-lib.nix { inherit inputs lib; };
      producerNames = [
        "capture-a11y"
        "capture-awair"
        "capture-clipboard"
        "capture-idle-inhibitors"
        "capture-kitty-scrollback"
        "capture-monitor"
        "capture-mpris"
        "capture-notifications"
        "capture-peripherals"
        "capture-primary"
        "capture-router"
        "capture-screen"
      ];
      evaluate =
        enabled: extra:
        testLib.evalTestSpec system {
          name = "typed-capture-producers";
          modules = [
            testLib.mountTmpfsRoots
            testLib.baseTestConfig
            {
              sinnix.services =
                lib.genAttrs producerNames (_: {
                  enable = enabled;
                })
                // {
                  capture-awair = {
                    enable = enabled;
                    intervalSec = 120;
                  };
                  capture-router = {
                    enable = enabled;
                    intervalSec = 600;
                  };
                };
            }
            extra
          ];
          assertions = _: [ ];
        };
      enabled = (evaluate true { }).config;
      disabled = (evaluate false { }).config;
      notifications =
        enabled.home-manager.users.${enabled.sinnix.user.name}.systemd.user.services.sinnix-capture-notifications;
      poller = enabled.systemd.user.services.sinnix-capture-awair;
      producerServices = lib.mapAttrsToList (
        name: producer:
        if producer.poll != null then
          enabled.systemd.user.services."sinnix-${name}".serviceConfig
        else
          enabled.home-manager.users.${enabled.sinnix.user.name}.systemd.user.services."sinnix-${name}".Service
      ) enabled.sinnix.capture.producers;
      badField = builtins.tryEval (
        builtins.deepSeq
          (evaluate true {
            sinnix.capture.producers.capture-awair.poll.unrecognizedTimer = 60;
          }).config.sinnix.capture.producers
          true
      );
      bothModes = builtins.tryEval (
        evaluate true {
          sinnix.capture.producers.capture-awair.stream = { };
        }
      );
      neitherMode = builtins.tryEval (
        evaluate false {
          sinnix.capture.producers.synthetic = {
            description = "Synthetic producer";
            execStart = "/synthetic/bin/writer";
            outputs = [ ];
          };
        }
      );
      invalidCadence = builtins.tryEval (
        builtins.deepSeq
          (evaluate true {
            sinnix.services.capture-awair.intervalSec = 61;
          }).config.systemd.user.timers.sinnix-capture-awair.timerConfig
          true
      );
    in
    {
      checks.capture-producers =
        assert builtins.all (
          service:
          service.Slice == "background.slice"
          && service.IOWeight == 20
          && service.Nice == 10
          && service.IOSchedulingPriority == 7
          && service.MemoryHigh == "6G"
          && service.MemoryMax == "8G"
        ) producerServices;
        assert enabled.systemd.user.timers.sinnix-capture-awair.timerConfig.OnCalendar == "*:0/2";
        assert builtins.length (builtins.attrNames enabled.sinnix.capture.producers) == 12;
        assert (builtins.head enabled.sinnix.runtime.units.capture-awair.captures).cadenceSeconds == 120;
        assert builtins.all (
          output: output.cadenceSeconds == 600
        ) enabled.sinnix.runtime.units.capture-router.captures;
        assert poller.serviceConfig.Type == "oneshot";
        assert poller.serviceConfig.UMask == "0077";
        assert notifications.Service.Type == "simple";
        assert notifications.Service.UMask == "0077";
        assert notifications.Unit.After == [ "default.target" ];
        assert !(notifications.Unit ? PartOf);
        assert notifications.Install.WantedBy == [ "default.target" ];
        assert
          (builtins.head enabled.sinnix.runtime.units.capture-notifications.captures).staleAfterSeconds
          == 86400;
        assert !(disabled.sinnix.capture.producers ? capture-awair);
        assert !(disabled.sinnix.capture.producers ? capture-notifications);
        assert !(disabled.sinnix.runtime.units ? capture-awair);
        assert !(disabled.systemd.user.services ? sinnix-capture-awair);
        assert
          !(
            disabled.home-manager.users.${disabled.sinnix.user.name}.systemd.user.services
            ? sinnix-capture-notifications
          );
        assert !badField.success && !bothModes.success && !neitherMode.success && !invalidCadence.success;
        pkgs.runCommand "capture-producers-check" { } ''touch "$out"'';
    };
}
