{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      testLib = import ../test-lib.nix { inherit inputs lib; };
      spec = testLib.mkFeatureTest {
        name = "mi-unlock-scheduled";
        feature = "sinnix.services.mi-unlock.enable";
        assertions = config:
          let
            service = config.systemd.user.services.sinnix-mi-unlock;
            timer = config.systemd.user.timers.sinnix-mi-unlock.timerConfig;
          in
          [
            {
              assertion = service.serviceConfig.Type == "simple";
              message = "mi-unlock must wait for the quota boundary in a simple service";
            }
            {
              assertion = service.serviceConfig.StateDirectory == "sinnix-mi-unlock";
              message = "mi-unlock must keep its grant sentinel in its state directory";
            }
            {
              assertion = service.serviceConfig.SuccessExitStatus == "75";
              message = "the ordinary quota refusal must remain successful service completion";
            }
            {
              assertion = service.unitConfig.ConditionPathExists == "!%S/sinnix-mi-unlock/granted";
              message = "mi-unlock must stop scheduling after a recorded grant";
            }
            {
              assertion = timer.OnCalendar == "*-*-* 17:25:00" && timer.AccuracySec == "1s";
              message = "mi-unlock must retain its boundary calendar and timer accuracy";
            }
            {
              assertion = !(timer ? Persistent) && config.systemd.user.timers.sinnix-mi-unlock.wantedBy == [ "timers.target" ];
              message = "mi-unlock must remain nonpersistent and enabled with user timers";
            }
          ];
      };
      evaluated = testLib.evalTestSpec system spec;
    in
    {
      checks.mi-unlock-scheduled = evaluated.config.system.build.toplevel;
    };
}
