# Usage census — evidence-joined audit of sinnix-owned artifact classes.
# Read-only joins of declaration inventories vs atuin/polylogue/journald
# evidence; JSONL to the machine capture lake. Absence of an evidence source
# degrades verdicts to `unknown`, never to a false `unused`.
{
  mkServiceModule,
  # Named although only the job function below uses it: the module system
  # injects _module.args entries (pkgs among them) only for formals the FILE
  # names, so a function-form job/surface that wants pkgs needs it declared
  # here, not just in its own pattern.
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "census";
  description = "Weekly evidence-joined usage census";
  surface =
    { config, ... }:
    {
      unit = "sinnix-census.service";
      resourceClass = "background-maintenance";
      observe.enable = true;
      workload = {
        class = "sacrificial";
        rationale = "Weekly read-only usage audit; rerunnable at will.";
      };
      captures = [
        {
          name = "usage-census";
          path = "${config.sinnix.paths.machineRoot}/usage-census.jsonl";
          # The weekly timer appends unconditionally -- there is no "nothing to
          # census" outcome -- so silence IS evidence here, unlike the lanes
          # whose content depends on the operator having done something.
          cadenceSeconds = 604800;
          # Two weeks: one missed run plus the 2h randomised delay.
          staleAfterSeconds = 1209600;
        }
      ];
    };
  job =
    {
      config,
      cfg,
      helpers,
      pkgs,
      ...
    }:
    {
      description = "Evidence-joined usage census";
      execStart = "${(helpers.mkSinnixPackagesFor pkgs).sinnix-census}/bin/sinnix-census --window-days ${toString cfg.windowDays}";
      # Runs as the operator: the evidence lives in the user's atuin DB,
      # polylogue archive, and user-manager journal.
      user = config.sinnix.user.name;
      timer = {
        onCalendar = "weekly";
        persistent = true;
        randomizedDelaySec = "2h";
      };
    };
  extraOptions = {
    windowDays = args.lib.mkOption {
      type = args.lib.types.int;
      default = 90;
      description = "Evidence lookback window in days.";
    };
  };
} args
