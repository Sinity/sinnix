{
  mkFeatureModule,
  pkgs,
  ...
}@args:
mkFeatureModule {
  path = [
    "dev"
    "reverseEngineering"
  ];
  description = "Native firmware and binary reverse-engineering workbench";
  configFn =
    {
      user,
      helpers,
      ...
    }:
    let
      scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
    in
    {
      home-manager.users.${user}.home.packages = [
        scriptPkgs.rea
        pkgs.ghidra
        pkgs.binwalk
        scriptPkgs.firmware-unblob
        pkgs.binutils
        pkgs.p7zip
      ];
    };
} args
