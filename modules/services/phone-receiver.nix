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
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  receiverPkg = scriptPkgs.sinnix-phone-receiver;
  capturesRoot = config.sinnix.paths.capturesRoot;

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
    # Only `speech`. The receiver's protocol accepts more kinds than that --
    # battery, thermal, location, health, sensor all parse -- but SpeechService
    # is the app's sole user of the stream port, and every other kind goes to
    # the app's own event log and reaches the lake through sinnix-phone-drain
    # instead. Declaring the other five would register capture lanes nothing is
    # designed to write, which is a standing false alarm rather than
    # monitoring. A kind that ever does start arriving here creates its own
    # lane on first write and can be declared then.
    #
    # eventDriven with no staleness budget: the phone pushes when it has
    # something, so silence measures the operator's day, not this service.
    captures = [
      {
        name = "phone-speech";
        path = "${capturesRoot}/phone-speech";
        eventDriven = true;
      }
    ];
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

      # Only the lanes something actually writes. This used to pre-create one
      # directory per accepted stream kind, because the captures root was
      # root-owned and CaptureWriter's own mkdir died with EACCES on the first
      # line of every kind. The root is owned by the user now
      # (modules/core.nix), so that workaround has no reason left -- and it
      # was leaving five permanently-empty directories (phone-battery,
      # -thermal, -location, -health, -sensor) in the lake for kinds that
      # reach it through sinnix-phone-drain instead, which is precisely the
      # standing false alarm the surface declaration above declines to make.
      # A kind that ever does arrive here creates its own lane on first write.
      systemd.tmpfiles.rules = [
        "d ${capturesRoot}/phone-speech 0755 ${username} users -"
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
