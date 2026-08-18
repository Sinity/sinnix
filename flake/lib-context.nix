{ inputs }:
let
  inherit (inputs.nixpkgs) lib;

  featureLib = import ../modules/lib/features.nix { inherit lib; };
  systemdLib = import ../modules/lib/systemd-hardening.nix { inherit lib; };
  overlayLib = import ../modules/lib/overlay-helpers.nix { inherit lib; };
  # mkCaptureLane builds ON mkServiceModule (callers do
  # `mkServiceModule (mkCaptureLane { ... }) args`) rather than wrapping it,
  # so it needs no reference to mkServiceModule itself -- just lib, like
  # featureLib/systemdLib/overlayLib.
  captureLaneLib = import ../modules/lib/capture-lane.nix { inherit lib; };
  # The one renderer for scheduled-oneshot jobs; mkServiceModule's `job`
  # argument is sugar over it, and multi-job or non-factory modules call it
  # directly as lib.sinnix.mkScheduledJob.
  scheduledJobLib = import ../modules/lib/scheduled-job.nix { inherit lib; };

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
        mkScheduledJob = scheduledJobLib;
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
    {
      # Every module in one host's evaluation shares the exact same `pkgs`
      # value, but `helpers.mkSinnixPackagesFor pkgs` used to be a plain
      # function call -- Nix memoises `import <path>` but never a function
      # APPLICATION, so ~40 call sites across modules/ each re-ran the whole
      # 95-script frontmatter discovery independently. Attaching the
      # registry as an attribute of `pkgs` itself makes it a member of the
      # same lazily-shared attrset every module already references, so it
      # evaluates once per host (each host's own `pkgs` fixed point gets its
      # own thunk -- this does not collapse sinnix-prime and sinnix-ethereal
      # into one registry, nor does it touch flake/tests/pkg-suites.nix's
      # deliberately separate unfreePkgs instantiation, which never goes
      # through this overlay). This is plumbing, not a package -- see
      # flake/overlay/package/default.nix's header for why an actual script
      # package would NOT belong here.
      nixpkgs.overlays = [
        (final: _prev: {
          sinnixScriptRegistry = import ./scripts.nix {
            inputs = moduleInputs;
            pkgs = final;
          };
        })
      ];
    }
  ];

  mkSharedSpecialArgs = specialInputs: {
    inputs = specialInputs;
    inherit (featureLib) mkFeatureModule mkServiceModule mkAiService;
    # capture-lane.nix exports the factory function directly (not wrapped in
    # an attrset), so this is a plain binding, not an inherit-from-set.
    mkCaptureLane = captureLaneLib;
    helpers = {
      inherit (featureLib) mkDotsFileFor;
      # pkgs.sinnixScriptRegistry is attached once per host by mkBaseModules'
      # overlay above; this stays a function of `pkgs` only so every existing
      # call site (`helpers.mkSinnixPackagesFor pkgs`) keeps working unchanged.
      mkSinnixPackagesFor = pkgs: pkgs.sinnixScriptRegistry.packageSet;
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
