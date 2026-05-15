# Transmission BitTorrent Client
#
# Downloads to torrentInbox/tdown, uses systemd hardening, and exposes RPC
# only on localhost for remote-only desktop clients.
# RPC accessible only on localhost (no auth required).
{
  mkServiceModule,
  lib,
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "transmission";
  description = "Transmission BitTorrent client";
  health = {
    unit = "transmission.service";
    type = "service";
    # Transmission is often intentionally stopped for disk maintenance.
    # Let the dedicated autostart timer handle boot startup; sentinel must
    # not fight manual stops or sparsification jobs.
    restartable = false;
  };
  extraOptions = {
    autoStart = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Start Transmission automatically after boot settles.";
    };
  };
  configFn =
    {
      cfg,
      config,
      lib,
      pkgs,
      ...
    }:
    let
      inherit (config.sinnix.paths) torrentInbox neoOuterRealm;
      username = config.sinnix.user.name;
      neoOuterRealmMount = "neo\\x2douter\\x2drealm.mount";
      transmissionConfigDir = "/var/lib/transmission/.config/transmission-daemon";
      torrentDownloadDir = "${torrentInbox}/tdown";
      torrentPartialDir = "${torrentInbox}/tdown_partial";
    in
    {
      services.transmission = {
        enable = true;
        openFirewall = true;
        package = pkgs.transmission_4;
        user = username;
        group = "users";
        settings = {
          script-torrent-done-enabled = false;
          ratio-limit-enabled = false;
          umask = 18;
          download-dir = torrentDownloadDir;
          incomplete-dir = torrentPartialDir;
          incomplete-dir-enabled = true;
          preallocation = 0;
          start-added-torrents = false;
          rpc-enabled = true;
          rpc-bind-address = "127.0.0.1";
          rpc-port = 9091;
          rpc-url = "/transmission/";
          # Auth disabled intentionally - RPC only accessible on localhost
          rpc-authentication-required = false;
          rpc-whitelist-enabled = false;
          rpc-host-whitelist = "127.0.0.1,localhost";
        };
      };

      systemd.tmpfiles.rules = lib.mkAfter [
        "d /var/lib/transmission/.config 0750 ${username} users -"
        "d ${transmissionConfigDir} 0750 ${username} users -"
        "f ${transmissionConfigDir}/queue.json 0644 ${username} users - []"
      ];

      systemd.services.transmission = {
        # why mkForce: gated behind PartOf=${neoOuterRealmMount} below.
        # The upstream nixos-transmission module attaches multi-user.target.
        wantedBy = lib.mkForce [ ];
        unitConfig.RequiresMountsFor = lib.unique [
          torrentInbox
          neoOuterRealm
        ];
        unitConfig.PartOf = [ neoOuterRealmMount ];
        after = [
          "network-online.target"
          neoOuterRealmMount
        ];
        wants = [ "network-online.target" ];
        serviceConfig = lib.mkMerge [
          (lib.sinnix.systemd.mkHardenedService {
            level = "strict";
            readWritePaths = [
              torrentInbox
              torrentPartialDir
              "/var/lib/transmission"
            ];
          })
          {
            # Transmission 4.1.1 uses RPC/session-info paths that are killed by
            # the generic syscall deny-list on this host. Keep filesystem,
            # namespace, privilege, and localhost RPC hardening, but do not use
            # seccomp as the failure mode for an interactive torrent daemon.
            SystemCallFilter = lib.mkForce [ ];
            # Cold Btrfs metadata lookups across large torrents can keep
            # Transmission busy checking payload paths before it sends READY=1.
            TimeoutStartSec = "15min";
            TimeoutStopSec = "5min";
            ExecStartPre = [
              "+${pkgs.coreutils}/bin/install -d -m 2775 -o ${username} -g users ${torrentInbox}"
              "+${pkgs.coreutils}/bin/install -d -m 2775 -o ${username} -g users ${torrentDownloadDir}"
              "+${pkgs.coreutils}/bin/install -d -m 2775 -o ${username} -g users ${torrentPartialDir}"
            ];
          }
          (lib.sinnix.systemd.mkRestartPolicy {
            strategy = "on-failure";
            delaySec = 10;
          })
        ];
      };

      systemd.services.transmission-autostart = {
        description = "Start Transmission after boot settles";
        after = [ "network-online.target" ];
        wants = [ "network-online.target" ];
        serviceConfig = {
          Type = "oneshot";
          Restart = "on-failure";
          RestartSec = "30s";
          ExecStart = pkgs.writeShellScript "transmission-autostart" ''
            set -euo pipefail

            if ${pkgs.systemd}/bin/systemctl is-active --quiet transmission.service; then
              exit 0
            fi

            exec ${pkgs.systemd}/bin/systemctl start transmission.service
          '';
        };
      };

      systemd.timers.transmission-autostart = {
        description = "Deferred Transmission startup";
        wantedBy = lib.optionals cfg.autoStart [ "timers.target" ];
        timerConfig = {
          OnBootSec = "30s";
          Unit = "transmission-autostart.service";
        };
      };

      systemd.services.transmission-sparsify = {
        description = "Punch holes in Transmission partial downloads";
        after = [ neoOuterRealmMount ];
        unitConfig = {
          RequiresMountsFor = [ torrentInbox ];
          PartOf = [ neoOuterRealmMount ];
        };
        path = with pkgs; [
          coreutils
          findutils
          systemd
          util-linux
        ];
        script = ''
          set -euo pipefail

          max_gib="''${TRANSMISSION_SPARSIFY_MAX_LOGICAL_GIB:-256}"
          force="''${TRANSMISSION_SPARSIFY_FORCE:-0}"
          plan="$(mktemp)"
          cleanup() {
            rm -f "$plan"
          }
          trap cleanup EXIT

          find ${lib.escapeShellArg torrentInbox} -xdev -type f -name "*.part" -print0 > "$plan"

          count=0
          bytes=0
          while IFS= read -r -d "" path; do
            size="$(stat -c %s -- "$path")"
            count="$((count + 1))"
            bytes="$((bytes + size))"
          done < "$plan"

          max_bytes="$((max_gib * 1024 * 1024 * 1024))"
          echo "transmission-sparsify: found $count partial file(s), $bytes logical byte(s), budget $max_gib GiB"

          if [ "$force" != 1 ] && [ "$bytes" -gt "$max_bytes" ]; then
            echo "transmission-sparsify: refusing scan above budget; set TRANSMISSION_SPARSIFY_FORCE=1 to override" >&2
            exit 78
          fi

          systemctl stop transmission.service transmission-autostart.timer transmission-autostart.service || true
          while IFS= read -r -d "" path; do
            echo "transmission-sparsify: punching holes in $path"
            fallocate -d -- "$path"
          done < "$plan"
        '';
        postStop = ''
          systemctl start transmission-autostart.timer transmission.service || true
        '';
        serviceConfig = {
          Type = "oneshot";
        };
      };
    };
} args
