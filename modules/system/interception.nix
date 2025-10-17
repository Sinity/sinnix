{ lib, pkgs, config, inputs, ... }:
let
  cfgBounce = config.services.interceptBounce;
  cfgScribe = config.services.scribeTap;

  inherit (lib) concatMap mkEnableOption mkIf mkMerge mkOption types;

  boolFlag = flag: cond: if cond then [ flag ] else [ ];
  valueFlag = flag: value:
    if value == null then
      [ ]
    else
      [ flag value ];
  repeatFlag = flag: values: concatMap (v: [ flag v ]) values;

  bounceArgs =
    [
      "${cfgBounce.package}/bin/intercept-bounce"
    ]
    ++ valueFlag "--debounce-time" cfgBounce.debounceTime
    ++ valueFlag "--near-miss-threshold-time" cfgBounce.nearMissThresholdTime
    ++ valueFlag "--log-interval" cfgBounce.logInterval
    ++ valueFlag "--ring-buffer-size" (
      if cfgBounce.ringBufferSize != null then toString cfgBounce.ringBufferSize else null
    )
    ++ valueFlag "--otel-endpoint" cfgBounce.otelEndpoint
    ++ repeatFlag "--debounce-key" cfgBounce.debounceKeys
    ++ repeatFlag "--ignore-key" cfgBounce.ignoreKeys
    ++ boolFlag "--log-bounces" cfgBounce.logBounces
    ++ boolFlag "--log-all-events" cfgBounce.logAllEvents
    ++ boolFlag "--verbose" cfgBounce.verbose
    ++ boolFlag "--stats-json" cfgBounce.statsJson
    ++ cfgBounce.extraArgs;

  scribeLogDir =
    if cfgScribe.logDir != null then cfgScribe.logDir else "${cfgScribe.dataDir}/logs";
  scribeSnapshotDir =
    if cfgScribe.snapshotDir != null then cfgScribe.snapshotDir else "${cfgScribe.dataDir}/snapshots";

  scribeArgs =
    [
      "${cfgScribe.package}/bin/scribe-tap"
      "--data-dir"
      cfgScribe.dataDir
      "--log-dir"
      scribeLogDir
      "--snapshot-dir"
      scribeSnapshotDir
      "--log-mode"
      cfgScribe.logMode
      "--context"
      cfgScribe.contextMode
      "--translate"
      cfgScribe.translateMode
      "--clipboard"
      cfgScribe.clipboardMode
    ]
    ++ valueFlag "--context-refresh" (
      if cfgScribe.contextRefresh != null then toString cfgScribe.contextRefresh else null
    )
    ++ valueFlag "--snapshot-interval" (
      if cfgScribe.snapshotInterval != null then toString cfgScribe.snapshotInterval else null
    )
    ++ valueFlag "--hyprctl" cfgScribe.hyprctl
    ++ valueFlag "--hypr-signature" cfgScribe.hyprSignaturePath
    ++ valueFlag "--hypr-user" cfgScribe.hyprUser
    ++ valueFlag "--xkb-layout" cfgScribe.xkbLayout
    ++ valueFlag "--xkb-variant" cfgScribe.xkbVariant
    ++ cfgScribe.extraArgs;
in
{
  options.services.interceptBounce = {
    enable = mkEnableOption "the intercept-bounce filter for interception-tools";

    package = mkOption {
      type = types.package;
      default = inputs.intercept-bounce.packages.${pkgs.system}.intercept-bounce;
      defaultText = "inputs.intercept-bounce.packages.\${pkgs.system}.intercept-bounce";
      description = "Package providing the intercept-bounce executable.";
    };

    debounceTime = mkOption {
      type = types.nullOr types.str;
      default = null;
      example = "40ms";
      description = "Duration window passed to --debounce-time.";
    };

    nearMissThresholdTime = mkOption {
      type = types.nullOr types.str;
      default = null;
      example = "100ms";
      description = "Threshold passed to --near-miss-threshold-time.";
    };

    logInterval = mkOption {
      type = types.nullOr types.str;
      default = null;
      example = "6h";
      description = "Interval used for --log-interval.";
    };

    logBounces = mkOption {
      type = types.bool;
      default = false;
      description = "Whether to pass --log-bounces.";
    };

    logAllEvents = mkOption {
      type = types.bool;
      default = false;
      description = "Whether to pass --log-all-events.";
    };

    verbose = mkOption {
      type = types.bool;
      default = false;
      description = "Enable verbose logging via --verbose.";
    };

    statsJson = mkOption {
      type = types.bool;
      default = false;
      description = "Emit JSON statistics via --stats-json.";
    };

    ringBufferSize = mkOption {
      type = types.nullOr types.int;
      default = null;
      description = "Optional size passed to --ring-buffer-size.";
    };

    otelEndpoint = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "OTLP endpoint passed to --otel-endpoint.";
    };

    debounceKeys = mkOption {
      type = types.listOf types.str;
      default = [ ];
      description = "List of key names forwarded as repeated --debounce-key.";
    };

    ignoreKeys = mkOption {
      type = types.listOf types.str;
      default = [ ];
      description = "List of key names forwarded as repeated --ignore-key.";
    };

    extraArgs = mkOption {
      type = types.listOf types.str;
      default = [ ];
      description = "Additional CLI arguments appended verbatim.";
    };

    commandString = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "Computed intercept-bounce command for interception pipelines.";
    };
  };

  options.services.scribeTap = {
    enable = mkEnableOption "scribe-tap keystroke mirror for interception-tools pipelines";

    package = mkOption {
      type = types.package;
      default = inputs.scribe-tap.packages.${pkgs.system}.default;
      defaultText = "inputs.scribe-tap.packages.\${pkgs.system}.default";
      description = "Package providing the scribe-tap executable.";
    };

    dataDir = mkOption {
      type = types.str;
      default = "/var/lib/scribe-tap";
      description = "Root directory for runtime artefacts stored by scribe-tap.";
    };

    logDir = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "Optional override for the log directory (defaults to dataDir/logs).";
    };

    snapshotDir = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "Optional override for the snapshot directory (defaults to dataDir/snapshots).";
    };

    logMode = mkOption {
      type = types.enum [ "events" "snapshots" "both" ];
      default = "both";
      description = "Log mode passed via --log-mode.";
    };

    contextMode = mkOption {
      type = types.enum [ "hyprland" "none" ];
      default = "hyprland";
      description = "Context provider passed via --context.";
    };

    translateMode = mkOption {
      type = types.enum [ "xkb" "raw" ];
      default = "xkb";
      description = "Translation mode forwarded to --translate.";
    };

    clipboardMode = mkOption {
      type = types.enum [ "auto" "off" ];
      default = "auto";
      description = "Clipboard handling passed to --clipboard.";
    };

    contextRefresh = mkOption {
      type = types.nullOr types.int;
      default = null;
      description = "Optional polling interval (seconds) passed to --context-refresh.";
    };

    snapshotInterval = mkOption {
      type = types.nullOr types.int;
      default = null;
      description = "Optional interval (seconds) passed to --snapshot-interval.";
    };

    hyprctl = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "Override path for hyprctl passed to --hyprctl.";
    };

    hyprSignaturePath = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "Path used for --hypr-signature.";
    };

    hyprUser = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "User whose Hyprland signature should be resolved.";
    };

    xkbLayout = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "Layout passed via --xkb-layout.";
    };

    xkbVariant = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "Variant passed via --xkb-variant.";
    };

    directoryMode = mkOption {
      type = types.str;
      default = "0750";
      description = "Filesystem mode applied to created runtime directories.";
    };

    directoryUser = mkOption {
      type = types.str;
      default = "root";
      description = "Owner user applied to runtime directories.";
    };

    directoryGroup = mkOption {
      type = types.str;
      default = "root";
      description = "Owner group applied to runtime directories.";
    };

    extraArgs = mkOption {
      type = types.listOf types.str;
      default = [ ];
      description = "Additional CLI arguments appended verbatim.";
    };

    commandString = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "Computed scribe-tap command for interception pipelines.";
    };
  };

  config = mkMerge [
    {
      services.interceptBounce.commandString = lib.escapeShellArgs bounceArgs;
      services.scribeTap.commandString = lib.escapeShellArgs scribeArgs;
    }
    (mkIf cfgScribe.enable {
      systemd.tmpfiles.rules = [
        "d ${cfgScribe.dataDir} ${cfgScribe.directoryMode} ${cfgScribe.directoryUser} ${cfgScribe.directoryGroup} -"
        "d ${scribeLogDir} ${cfgScribe.directoryMode} ${cfgScribe.directoryUser} ${cfgScribe.directoryGroup} -"
        "d ${scribeSnapshotDir} ${cfgScribe.directoryMode} ${cfgScribe.directoryUser} ${cfgScribe.directoryGroup} -"
      ];
    })
  ];
}
