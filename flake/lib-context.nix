{ inputs }:
let
  inherit (inputs.nixpkgs) lib;

  featureLib = import ../modules/lib/features.nix { inherit lib; };
  systemdLib = import ../modules/lib/systemd-hardening.nix { inherit lib; };
  overlayLib = import ../modules/lib/overlay-helpers.nix { inherit lib; };

  extendedLib = lib.extend (
    _final: _prev: {
      sinnix = {
        inherit (featureLib) mkPAMLimits mkAutoImports mkBundleModule;
        systemd = systemdLib;
        overlay = overlayLib;
      };
    }
  );

  mkBaseModules = moduleInputs: [
    moduleInputs.agenix.nixosModules.default
    moduleInputs.stylix.nixosModules.stylix
    moduleInputs.impermanence.nixosModules.impermanence
    (import ./overlay {
      inputs = moduleInputs;
      inherit overlayLib;
    })
  ];

  mkSharedSpecialArgs = specialInputs: {
    inputs = specialInputs;
    inherit (featureLib) mkFeatureModule mkServiceModule;
    helpers = {
      inherit (featureLib) mkDotsFileFor;
      mkSinnixPackagesFor =
        pkgs:
        (import ./scripts.nix {
          inputs = specialInputs;
          inherit pkgs;
        }).packageSet;
    };
  };
in
{
  inherit
    lib
    featureLib
    systemdLib
    overlayLib
    extendedLib
    mkBaseModules
    mkSharedSpecialArgs
    ;
}
