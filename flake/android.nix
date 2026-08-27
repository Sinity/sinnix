{ inputs, ... }:
{
  flake.androidConfigurations.redmi-note-11 = inputs.nix-android.lib.mkDevice {
    system = "x86_64-linux";
    modules = [ ../devices/android/redmi-note-11.nix ];
    lockFile = ../devices/android/redmi-note-11-apps.lock.json;
  };

  perSystem =
    { system, ... }:
    {
      packages.android-rebuild = inputs.nix-android.packages.${system}.android-rebuild;
    };
}
