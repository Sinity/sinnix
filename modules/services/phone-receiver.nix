# The always-listening end of the phone's push: line-delimited JSON, one lane
# per `kind`, currently VAD-gated speech utterances and the app's mirrored
# event stream.
#
# The service is persistent; the CONNECTIONS are not, and this header claimed
# otherwise until 2026-08-17. The app opens a fresh socket per flush and
# closes it, deliberately -- a phone sleeps, roams and changes networks
# mid-sentence, so a socket held across all of that is usually stale in a way
# neither end has noticed. Nothing here needs changing for that; it just is
# not the design the first paragraph used to describe.
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
  # The receiver files each lane under the root it was given; since the
  # subject recut that is machineRoot, and the local name says so rather than
  # still saying "captures".
  laneRoot = config.sinnix.paths.machineRoot;

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
    # Two of the kinds this port accepts, and only two. The protocol parses
    # more (battery, thermal, location, health, sensor), but nothing sends
    # them -- those readings go to the app's own event log, which arrives here
    # wrapped as `estate_event` and separately through the drain. Declaring a
    # lane nothing writes is a standing false alarm rather than monitoring; a
    # kind that does start arriving creates its lane on first write and can be
    # declared then.
    captures = [
      {
        # eventDriven with no staleness budget: the phone pushes when it has
        # something to say, so silence measures the operator's day rather
        # than this service.
        name = "phone-speech";
        path = "${laneRoot}/phone-speech";
        eventDriven = true;
      }
      {
        # The app's live event mirror. Undeclared until 2026-08-17 because
        # nothing read it -- a complete lane with no consumer. It has one now:
        # `sinnix-phone app-status` answers from this lane when adb is down,
        # which is when the question matters most, so the lane's freshness is
        # something the estate should notice going stale rather than discover
        # while debugging a silent phone.
        #
        # Half an hour, against a mirror that flushes every 20 seconds: the
        # budget has to absorb an ordinary phone-off-the-tailnet stretch
        # without crying, while still being far tighter than the drain's day.
        name = "phone-estate_event";
        path = "${laneRoot}/phone-estate_event";
        cadenceSeconds = 20;
        staleAfterSeconds = 1800;
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
        "d ${laneRoot}/phone-speech 0755 ${username} users -"
        # Raw utterance audio, kept whether or not transcription succeeded:
        # audio can be re-transcribed by a better engine later, a transcript
        # cannot be un-lost.
        "d ${laneRoot}/phone/speech 0755 ${username} users -"
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
                ExecStart = "${receiverPkg}/bin/sinnix-phone-receiver --host \${SINNIX_PHONE_RECEIVER_BIND} --port ${toString port} --capture-root ${laneRoot}";
                Restart = "on-failure";
                RestartSec = "5s";
              };
            };
            Install.WantedBy = [ "default.target" ];
          };
        };
    };
} args
