# Persistent receiver for the phone's always-on telemetry push: the phone
# maintains one long-lived TCP connection to this service and streams
# structured telemetry (battery, sensors, later VAD-gated audio)
# continuously.
#
# Binds the tailscale0 address only, same pattern as sinnix.services.hub --
# never 0.0.0.0, opened per-interface so a LAN peer never reaches it.
{
  mkServiceModule,
  helpers,
  pkgs,
  lib,
  config,
  ...
}@args:
let
  cfg = config.sinnix.services.phone-receiver;
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  receiverPkg = scriptPkgs.sinnix-phone-receiver;
  capturesRoot = config.sinnix.paths.capturesRoot;

  # The kinds the phone actually pushes. Named rather than inferred because
  # each one needs a directory the receiver's user can write: the captures root
  # is root-owned, and CaptureWriter creates `<root>/phone-<kind>` on first
  # write. Nothing ever reached this service before, so that permission error
  # had never once been hit -- the first real utterance found it immediately.
  # A kind not listed here still parses and is still logged; only its lane
  # cannot be created, which is a loud failure rather than a silent one.
  streamKinds = [
    "speech"
    "battery"
    "thermal"
    "location"
    "health"
    "sensor"
  ];
  tailscaleInterface = "tailscale0";
  port = helpers.data.ports.phoneStream;

  resolveBind = pkgs.writeShellScript "sinnix-phone-receiver-resolve-bind" ''
    set -euo pipefail
    target="$1"
    ${pkgs.coreutils}/bin/mkdir -p "$(${pkgs.coreutils}/bin/dirname "$target")"
    for _ in $(${pkgs.coreutils}/bin/seq 1 60); do
      address="$(${pkgs.iproute2}/bin/ip -4 -o addr show dev ${tailscaleInterface} 2>/dev/null \
        | ${pkgs.gawk}/bin/awk '{print $4}' \
        | ${pkgs.coreutils}/bin/cut -d/ -f1 \
        | ${pkgs.coreutils}/bin/head -n1)"
      if [ -n "''${address:-}" ]; then
        ${pkgs.coreutils}/bin/printf 'SINNIX_PHONE_RECEIVER_BIND=%s\n' "$address" > "$target"
        exit 0
      fi
      ${pkgs.coreutils}/bin/sleep 2
    done
    echo "sinnix-phone-receiver: ${tailscaleInterface} has no IPv4 address; refusing to start" >&2
    exit 1
  '';
in
mkServiceModule {
  name = "phone-receiver";
  description = "Persistent TCP receiver for the phone's always-on telemetry push";
  surface = {
    unit = "sinnix-phone-receiver.service";
    manager = "user";
    resourceClass = "capture-runtime";
    observe = {
      enable = true;
      restartable = true;
    };
    # One entry per stream kind. Declaring none meant five of the six lanes
    # sat at zero files with nothing able to notice: the sentinel cannot
    # report on a lane that was never declared.
    #
    # eventDriven with no staleness budget, because the phone pushes when it
    # has something and silence measures the phone's activity, not this
    # service's health. What that cannot catch, `lane-empty` in
    # sinnix-sandbox-audit does.
    captures = map (kind: {
      name = "phone-${kind}";
      path = "${capturesRoot}/phone-${kind}";
      eventDriven = true;
    }) streamKinds;
  };
  configFn =
    { config, ... }:
    let
      username = config.sinnix.user.name;
    in
    {
      assertions = [
        {
          assertion = config.sinnix.services.tailscale.enable;
          message = "sinnix.services.phone-receiver requires sinnix.services.tailscale.enable -- the tailnet is its only security boundary.";
        }
      ];

      networking.firewall.interfaces.${tailscaleInterface}.allowedTCPPorts = [ port ];

      # One directory per stream kind, owned by the user the receiver runs as.
      # The captures root is root-owned and CaptureWriter creates its lane
      # directory on first write, so without these the very first line of every
      # kind dies with EACCES -- which is exactly what happened the first time
      # anything was ever pushed at this service.
      systemd.tmpfiles.rules =
        map (kind: "d ${capturesRoot}/phone-${kind} 0755 ${username} users -") streamKinds
        ++ [
          # Raw utterance audio, kept whether or not transcription succeeded:
          # audio can be re-transcribed by a better engine later, a transcript
          # cannot be un-lost.
          "d ${capturesRoot}/phone/speech 0755 ${username} users -"
        ];

      home-manager.users.${username} =
        { ... }:
        {
          systemd.user.services.sinnix-phone-receiver = {
            Unit = {
              Description = "Persistent TCP receiver for the phone's always-on telemetry push";
              After = [ "network-online.target" ];
            };
            Service = lib.sinnix.mkRuntimeServiceConfig {
              runtimeInventory = config.sinnix.runtime.inventory;
              unit = "sinnix-phone-receiver.service";
              overrides = {
                Type = "simple";
                ExecStartPre = "${resolveBind} %t/sinnix/phone-receiver-bind.env";
                EnvironmentFile = "-%t/sinnix/phone-receiver-bind.env";
                ExecStart = "${receiverPkg}/bin/sinnix-phone-receiver --host \${SINNIX_PHONE_RECEIVER_BIND} --port ${toString port} --capture-root ${capturesRoot}";
                Restart = "on-failure";
                RestartSec = "5s";
              };
            };
            Install.WantedBy = [ "default.target" ];
          };
        };
    };
} args
