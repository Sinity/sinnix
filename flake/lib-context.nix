{ inputs }:
let
  inherit (inputs.nixpkgs) lib;

  featureLib = import ../modules/lib/features.nix { inherit lib; };
  systemdLib = import ../modules/lib/systemd-hardening.nix { inherit lib; };
  overlayLib = import ../modules/lib/overlay-helpers.nix { inherit lib; };

  # Pure data tables under flake/data/ are evaluated once at flake-init and
  # shared by reference across every host evaluation. NixOS modules consume
  # them via specialArgs.helpers.data — no per-host `import` of the same file.
  data = {
    mcpRegistry = import ./data/mcp-registry.nix { inherit lib; };
    runtimeDefaults = import ./data/runtime-defaults.nix { inherit lib; };
    localModels = import ./data/local-models.nix { inherit lib; };
    agentLanes = import ./data/agent-lanes.nix;
    # checkedPorts, not the raw table: consuming the data is what forces the
    # uniqueness assertion below, so a duplicate cannot slip through by being
    # lazily never evaluated.
    ports = checkedPorts;
  };

  # Flatten the nested port table to a list of ints and refuse to evaluate if
  # any number is claimed twice. Two services silently sharing a port is only
  # discoverable at activation otherwise, as an "Address already in use" on
  # whichever unit loses the race.
  rawPorts = import ./data/ports.nix;
  portNumbers = lib.collect builtins.isInt rawPorts;
  # NB: subtractLists is the wrong tool here -- it removes *every* occurrence
  # of a value, so a doubled port cancels itself out and reads as unique.
  duplicatePorts = lib.unique (lib.filter (p: lib.count (x: x == p) portNumbers > 1) portNumbers);
  checkedPorts = lib.throwIf (duplicatePorts != [ ]) (
    "flake/data/ports.nix allocates the same port more than once: "
    + lib.concatMapStringsSep ", " toString duplicatePorts
  ) rawPorts;

  extendedLib = lib.extend (
    _final: _prev: {
      sinnix = {
        inherit (featureLib) mkPAMLimits mkSecretLookup mkAutoImports;
        systemd = systemdLib;
        inherit (systemdLib) mkRuntimeServiceConfig;
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
    inherit (featureLib) mkFeatureModule mkServiceModule mkAiService;
    helpers = {
      inherit (featureLib) mkDotsFileFor;
      mkSinnixPackagesFor =
        pkgs:
        (import ./scripts.nix {
          inputs = specialInputs;
          inherit pkgs;
        }).packageSet;
      inherit data;
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
