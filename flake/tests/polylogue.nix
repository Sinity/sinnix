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

      sentinelDataDir = "/tmp/sinnix-polylogue-service-sentinel";
      archiveRootSpec = mkServiceTest {
        name = "polylogue-archive-root";
        service = "polylogue";
        extraModules = [
          (_: {
            sinnix.services.polylogue.dataDir = sentinelDataDir;
          })
        ];
        assertions = _config: [ ];
      };
      archiveRootEvaluated = evalTestSpec system archiveRootSpec;
      enrichmentSpec = mkServiceTest {
        name = "enrichment-polylogue-root";
        service = "enrichment-loop";
        extraModules = [
          (_: {
            sinnix.services.polylogue.dataDir = sentinelDataDir;
          })
        ];
        assertions = _config: [ ];
      };
      enrichmentEvaluated = evalTestSpec system enrichmentSpec;
      enrichmentService = enrichmentEvaluated.config.systemd.user.services.sinnix-enrichment-loop;
      polylogueTmpfiles = archiveRootEvaluated.config.systemd.tmpfiles.rules;
      archiveInventory = archiveRootEvaluated.config.sinnix.runtime.inventory.polylogue;
      enrichmentReadWritePaths = enrichmentService.serviceConfig.ReadWritePaths;
      enrichmentArchiveRoot = enrichmentService.environment.POLYLOGUE_ARCHIVE_ROOT;

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
        polylogue-archive-root =
          pkgs.runCommand "sinnix-polylogue-archive-root-check"
            {
              inherit sentinelDataDir;
              nativeBuildInputs = [ pkgs.jq ];
              actualTmpfiles = builtins.toJSON polylogueTmpfiles;
            }
            ''
              jq -e --arg root "$sentinelDataDir" '
                index("d \($root)/inbox 0755 sinity users -") != null and
                index("L+ \($root)/inbox/chatgpt - - - - /realm/data/ai/chatlog/raw/chatgpt") != null and
                index("L+ \($root)/inbox/claude - - - - /realm/data/ai/chatlog/raw/claude") != null
              ' <<<"$actualTmpfiles" >/dev/null
              touch "$out"
            '';
        enrichment-polylogue-root =
          pkgs.runCommand "sinnix-enrichment-polylogue-root-check"
            {
              inherit sentinelDataDir enrichmentArchiveRoot;
              nativeBuildInputs = [ pkgs.jq ];
              actualReadWritePaths = builtins.toJSON enrichmentReadWritePaths;
            }
            ''
              test "$enrichmentArchiveRoot" = "$sentinelDataDir"
              jq -e --arg hook "$sentinelDataDir/hooks" 'index($hook) != null' <<<"$actualReadWritePaths" >/dev/null
              if jq -e 'index("/realm/state/polylogue/hooks") != null' <<<"$actualReadWritePaths" >/dev/null; then
                echo "enrichment hardening retained the default Polylogue hook root" >&2
                exit 1
              fi
              touch "$out"
            '';
        polylogue-runtime-inventory =
          pkgs.runCommand "sinnix-polylogue-runtime-inventory-check"
            {
              inherit sentinelDataDir;
              nativeBuildInputs = [ pkgs.jq ];
              actual = builtins.toJSON archiveInventory;
            }
            ''
              jq -e --arg root "$sentinelDataDir" '
                .archiveRoot == $root and
                (.databaseTiers == ["index.db", "source.db", "embeddings.db", "ops.db", "audit.db", "user.db"]) and
                (.projections | any(.kind == "compatibility" and .source == $root))
              ' <<<"$actual" >/dev/null
              touch "$out"
            '';
      };
    };
}
