# Exercise the generated channel with neutral local Maildirs. No IMAP server,
# credential, operator mailbox or live service is used by this check.
{ inputs, ... }:
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      lib = inputs.nixpkgs.lib;
      testLib = import ../test-lib.nix { inherit inputs lib; };
      spec = testLib.mkServiceTest {
        name = "capture-mail";
        service = "capture-mail";
        extraModules = [ { sinnix.services.capture-mail.imapUser = "fixture@example.invalid"; } ];
        assertions = config: [
          {
            assertion = config.sinnix.services.capture-mail.intervalSec == 900;
            message = "The mail mirror must retain its 15-minute default cadence.";
          }
          {
            assertion =
              map (
                capture: lib.getAttrs [ "name" "path" "cadenceSeconds" "staleAfterSeconds" ] capture
              ) config.sinnix.runtime.surfaces.capture-mail.captures == [
                {
                  name = "mail";
                  path = config.sinnix.paths.capturePaths.mail;
                  cadenceSeconds = 900;
                  staleAfterSeconds = 7200;
                }
              ];
            message = "The native Maildir must be the registered capture surface.";
          }
        ];
      };
      evaluated = testLib.evalTestSpec system spec;
      unit = evaluated.config.systemd.user.services.sinnix-capture-mail;
      configPath = builtins.elemAt (lib.splitString " " unit.serviceConfig.ExecStart) 1;
    in
    {
      checks.capture-mail =
        assert evaluated.options.sinnix.services.capture-mail.enable.default == false;
        pkgs.runCommand "capture-mail-check"
          {
            nativeBuildInputs = [
              pkgs.python3
              pkgs.isync
            ];
            MAIL_CONFIG = configPath;
            MAIL_UNIT = builtins.toJSON unit.serviceConfig;
            MAIL_TIMER = builtins.toJSON evaluated.config.systemd.user.timers.sinnix-capture-mail.timerConfig;
          }
          ''
            python3 ${./capture_mail.py}
            touch "$out"
          '';
    };
}
