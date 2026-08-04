# Polylogue service module evaluation checks.
#
# The memory-budget check evaluates both the default and an overridden budget,
# proving the one declared value drives MemoryHigh, MemoryMax, and the daemon's
# byte-valued environment export together.
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

      defaultSpec = mkServiceTest {
        name = "polylogue-memory-budget-default";
        service = "polylogue";
        assertions = _config: [ ];
      };
      overriddenSpec = mkServiceTest {
        name = "polylogue-memory-budget-overridden";
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
        polylogue-memory-budget-default = mkMemoryBudgetCheck {
          name = "polylogue-memory-budget-default-check";
          spec = defaultSpec;
          expectedHigh = "14G";
          expectedMax = "18G";
          expectedBudgetBytes = "17179869184";
        };
        polylogue-memory-budget-overridden = mkMemoryBudgetCheck {
          name = "polylogue-memory-budget-overridden-check";
          spec = overriddenSpec;
          expectedHigh = "21G";
          expectedMax = "27G";
          expectedBudgetBytes = "25769803776";
        };
      };
    };
}
