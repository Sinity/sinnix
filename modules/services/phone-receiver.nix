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
    # No `captures[]` entry: this surface demuxes into dynamically-named
    # phone-<kind> lanes rather than one fixed lane, so a single static
    # staleAfterSeconds entry doesn't fit the sentinel's per-lane model.
    # Fast-follow: register one captures[] entry per known kind (battery,
    # sensor) once the phone-side client's kind set stabilizes.
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
