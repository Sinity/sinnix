{ lib }:
let
  mkFeatureModule =
    {
      path,
      description,
      enableDefault ? false,
      extraOptions ? { },
      configFn,
    }:
    args@{ config, ... }:
    let
      featurePath = [ "sinnix" "features" ] ++ path;
      optionsForPath = extraOptions // {
        enable = (lib.mkEnableOption description) // { default = enableDefault; };
      };
      cfg = lib.getAttrFromPath featurePath config;
    in
    {
      options = lib.setAttrByPath featurePath optionsForPath;
      config = lib.mkIf cfg.enable (configFn (args // { inherit cfg; }));
    };
in
{
  inherit mkFeatureModule;
}
