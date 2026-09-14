# The collector only records the cgroups it is told to sample, so a pool slice
# that is absent from `--cgroups` is not "low priority telemetry" -- it is
# unmeasurable. The agentctl pool slices were in exactly that state while their
# MemoryHigh values were the thing gating test parallelism, and the bug was a
# hand-kept second copy of the pool list inside the telemetry module.
#
# Provably fails when: a slice declared in runtime-defaults' agentctl-* family
# stops reaching the collector's --cgroups argument (verified by dropping
# agentctl-pytest-heavy from the derived list), when a pool's cgroup path stops
# nesting under its parent slice, or when the desktop-reservation slices the
# job plane is sized against fall out of the sampled set.
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      testLib = import ../test-lib.nix { inherit inputs lib; };
      inherit (testLib) evalTestSpec mkFeatureTest;

      runtimeDefaults = import ../data/runtime-defaults.nix { inherit lib; };
      # Read the expectation from the slice registry, not from a list restated
      # here: a new pool must fail this check until it is sampled.
      poolSliceNames = lib.filter (name: lib.hasPrefix "agentctl-" name) (
        lib.attrNames runtimeDefaults.slices.user
      );
      userSliceRoot = "/user.slice/user-1000.slice/user@1000.service";
      expectedPoolPath =
        name:
        "${userSliceRoot}/${
          lib.concatStringsSep "/" (
            lib.imap1 (
              index: _: "${lib.concatStringsSep "-" (lib.take index (lib.splitString "-" name))}.slice"
            ) (lib.splitString "-" name)
          )
        }";
      expectedSpecs = map (name: "user.${name}|user|${expectedPoolPath name}") poolSliceNames ++ [
        "user.app|user|${userSliceRoot}/app.slice"
        "user.session|user|${userSliceRoot}/session.slice"
        "user.desktop-shell|user|${userSliceRoot}/desktop-shell.slice"
      ];

      spec = mkFeatureTest {
        name = "machine-telemetry-cgroups";
        feature = "sinnix.services.machine-telemetry.enable";
        assertions =
          config:
          let
            rendered = toString config.systemd.services.machine-telemetry.serviceConfig.ExecStart;
          in
          [
            {
              assertion = poolSliceNames != [ ];
              message = "the runtime slice registry must declare agentctl pool slices for this check to mean anything";
            }
          ]
          ++ map (want: {
            assertion = lib.hasInfix want rendered;
            message = "machine-telemetry must sample the cgroup spec ${want}; without it the slice cannot be sized from evidence";
          }) expectedSpecs;
      };
      evaluated = evalTestSpec system spec;
      renderedExecStart = toString evaluated.config.systemd.services.machine-telemetry.serviceConfig.ExecStart;
    in
    {
      checks.machine-telemetry-cgroups = pkgs.runCommand "machine-telemetry-cgroups-check" { } ''
        cat > exec-start <<'EOF_EXEC_START'
        ${renderedExecStart}
        EOF_EXEC_START
        ${lib.concatMapStringsSep "\n" (want: ''
          grep -qF ${lib.escapeShellArg want} exec-start || {
            echo "FAIL: machine-telemetry does not sample ${want}"
            cat exec-start
            exit 1
          }
        '') expectedSpecs}
        touch "$out"
      '';
    };
}
