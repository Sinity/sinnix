{
  mkFeatureModule,
  config,
  lib,
  pkgs,
  inputs,
  ...
}@args:
mkFeatureModule {
  path = [
    "cli"
    "stability-lab"
  ];
  description = "Persistent hardware stability test runner";
  configFn =
    {
      config,
      user,
      pkgs,
      inputs,
      lib,
      ...
    }:
    let
      scriptPkgs = inputs.self.packages.${pkgs.stdenv.hostPlatform.system};
      rebootNoMorePkgs = inputs."reboot-no-more".packages.${pkgs.stdenv.hostPlatform.system};
      rebootNoMorePkg = rebootNoMorePkgs.reboot-no-more or rebootNoMorePkgs.default;
      inherit (config.sinnix.paths) capturesRoot;
      userGroup = config.users.users.${user}.group or user;
      runRoot = "${capturesRoot}/stability-lab";
      triggerRoot = "${capturesRoot}/launch-trigger";
    in
    {
      home-manager.users.${user} =
        { ... }:
        {
          home.packages = [
            scriptPkgs.launch-trigger-capture
            scriptPkgs.stability-lab
            rebootNoMorePkg
          ];
          home.sessionVariables = {
            SINNIX_STABILITY_ROOT = runRoot;
            SINNIX_TRIGGER_CAPTURE_ROOT = triggerRoot;
          };
        };

      systemd.tmpfiles.rules = lib.mkAfter [
        "d ${runRoot} 0750 ${user} ${userGroup} -"
        "d ${triggerRoot} 0750 ${user} ${userGroup} -"
      ];
    };
} args
