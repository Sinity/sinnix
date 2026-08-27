{ inputs, ... }:
{
  flake.nixOnDroidConfigurations.redmi-note-11 = inputs.nix-on-droid.lib.nixOnDroidConfiguration {
    pkgs = import inputs.nixpkgs { system = "aarch64-linux"; };
    modules = [ ../devices/android/redmi-note-11-userland.nix ];
  };
}
