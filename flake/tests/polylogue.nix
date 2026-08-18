# Polylogue service module evaluation checks.
#
# The memory-budget check proves that one declared budget drives MemoryHigh,
# MemoryMax, and the daemon's byte-valued environment export together. It uses
# an explicitly overridden budget rather than the module default: pinning the
# default's derived values here would only force a two-place edit whenever the
# default moves, without testing anything the override does not.
#
# Provably fails when: the module stops deriving any of the three outputs from
# memoryBudgetGiB (verified by changing the MemoryHigh factor in
# modules/services/polylogue.nix).
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
      inherit (testLib)
        evalTestSpec
        hmFor
        mkServiceTest
        ;

      mkMemoryBudgetCheck =
        {
          name,
          spec,
          expectedHigh,
          expectedMax,
          expectedBudgetBytes,
        }:
        let
          evaluated = evalTestSpec system spec;
          service = (hmFor evaluated.config).systemd.user.services.polylogued.Service;
          budgetEnvironment = lib.findFirst (
            entry: lib.hasPrefix "POLYLOGUE_MEMORY_BUDGET_BYTES=" entry
          ) "" service.Environment;
        in
        pkgs.runCommand "sinnix-${name}"
          {
            inherit expectedHigh expectedMax expectedBudgetBytes;
            actualHigh = service.MemoryHigh;
            actualMax = service.MemoryMax;
            actualBudgetEnvironment = budgetEnvironment;
          }
          ''
            test "$actualHigh" = "$expectedHigh"
            test "$actualMax" = "$expectedMax"
            test "$actualBudgetEnvironment" = "POLYLOGUE_MEMORY_BUDGET_BYTES=$expectedBudgetBytes"
            touch "$out"
          '';

      overriddenSpec = mkServiceTest {
        name = "polylogue-memory-budget";
        service = "polylogue";
        extraModules = [
          (_: {
            sinnix.services.polylogue.memoryBudgetGiB = 24;
          })
        ];
        assertions = _config: [ ];
      };
    in
    {
      checks = {
        polylogue-memory-budget = mkMemoryBudgetCheck {
          name = "polylogue-memory-budget-check";
          spec = overriddenSpec;
          expectedHigh = "21G";
          expectedMax = "27G";
          expectedBudgetBytes = "25769803776";
        };
      };
    };
}
