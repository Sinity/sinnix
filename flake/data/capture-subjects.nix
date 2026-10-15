# Capture-scope-v1 subject membership. Lane IDs are exact runtime declarations.
# Optional lanes are projected only when enabled; new lanes need explicit membership.
{
  activity = [
    "activitywatch"
    "a11y"
    "audio-index"
    "clipboard"
    "kitty-scrollback"
    "mpris"
    "notifications"
    "primary"
    "screen-frames"
    "keylog"
    "webhistory"
    "phone-ambient"
    "phone-events"
    "browser-nav-edges"
    "reading-stack"
    "transcripts"
    "video-resolve"
    "asciinema"
    "screenshot"
  ];
  ai = [
    "borg-polylogue-state-archive"
  ];
  comms = [
    "mail"
    "phone-calls"
    "comms-irc"
  ];
  health = [
    "xiaomi-cloud"
  ];
  self = [
    "phone-speech"
    "steering"
  ];
  machine = [
    "borg-realm-independent-full-audit"
    "borg-machine-telemetry-dumps"
    "borg-persist-archive"
    "borg-realm-archive"
    "borg-sinex-blobs-archive"
    "borg-drill"
    "borg-integrity-receipt"
    "audio-devices"
    "audio-topology"
    "environment"
    "monitor"
    "netflow"
    "peripherals-logitech"
    "peripherals-bt-battery"
    "peripherals-bt-audio"
    "router-leases"
    "router-associations"
    "router-nlbw"
    "router-syslog"
    "config-drift"
    "fs-index"
    "machine-telemetry"
    "machine-telemetry-sqlite-structural-verification"
    "phone-logcat"
    "audit-denials"
    "borg-beads-drill"
    "url-ledger-state"
    "url-ledger-coverage"
    "usage-census"
  ];
}
