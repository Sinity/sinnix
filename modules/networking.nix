# Core networking configuration
#
# Provides:
# - NetworkManager with systemd-resolved stub/cache
# - DNS resolution via router (sinnix-gw handles DoH upstream to Cloudflare + Quad9)
# - Hardened OpenSSH (no passwords, no root login, rate-limited, verbose logging)
# - NTP via router with nixos.pool.ntp.org fallback
# - Mosh for resilient remote sessions
# - Bluetooth support with experimental features (desktop only)
{
  lib,
  pkgs,
  config,
  ...
}:
let
  inherit (config.sinnix.machine) isDesktop;
  desktopNetworkingPackages = [
    pkgs.networkmanagerapplet
    pkgs.bluez
    pkgs.bluez-tools
  ];
  networkingToolPackages = with pkgs; [
    iputils
    ethtool
    iftop
    iperf3
  ];

  cfg = config.sinnix.networking;
in
{
  options.sinnix.networking.enable = lib.mkOption {
    type = lib.types.bool;
    default = true;
    description = "Enable core networking configuration (NetworkManager, DNS, SSH)";
  };

  config = lib.mkIf cfg.enable {
    networking = {
      networkmanager = {
        enable = true;
        dns = "systemd-resolved";
        # DNS authority is on the router (sinnix-gw) which runs https-dns-proxy → Cloudflare DoH.
        # DHCP advertises the router as DNS server; we accept that here.
        # No need to override with ignore-auto-dns anymore.
      };
    };

    # Don't gate boot on full network startup. nm-online -s waits for ALL
    # autoconnect profiles to complete or time out (60s budget); cold-boot
    # WiFi WPA handshake or DHCP renewal regularly trips that. On a
    # desktop nothing critical depends on the unit — disabling avoids the
    # boot-time failure that lingers in `systemctl --failed`.
    systemd.services.NetworkManager-wait-online.enable = false;

    services = {
      # systemd-resolved provides the local stub resolver and .lan handling.
      # The router remains the DNS authority and already forwards upstream via DoH.
      resolved = {
        enable = true;
        settings = {
          Resolve = {
            # Avoid duplicate validation on the workstation.
            DNSSEC = false;
            # Emit an explicit blank fallback list so compiled-in public resolvers stay disabled.
            FallbackDNS = "";
            # Avahi owns local mDNS service discovery on this host.
            MulticastDNS = false;
            # Resolve .lan names via the router's dnsmasq.
            Domains = [ "~lan" ];
          };
        };
      };

      # Use router as NTP server (it syncs via ntpd from upstream).
      # Reduces external traffic and provides consistent time across the LAN.
      timesyncd = {
        enable = true;
        servers = [ "192.168.1.1" ];
        extraConfig = ''
          FallbackNTP=0.nixos.pool.ntp.org 1.nixos.pool.ntp.org
        '';
      };

      openssh = {
        enable = true;
        settings = {
          UseDns = false;
          GSSAPIAuthentication = false;
          PermitRootLogin = lib.mkDefault "no";
          PasswordAuthentication = false;
          KbdInteractiveAuthentication = false;
          LogLevel = "VERBOSE";
          # Rate-limit unauthenticated connections to slow brute-force attempts
          MaxStartups = "3:50:10";
          LoginGraceTime = 30;
        };
      };

    };

    programs.mosh.enable = true;

    # sshd hardening handled by nixpkgs - custom seccomp filters break it.
    systemd.services.sshd.serviceConfig = lib.sinnix.mkRuntimeServiceConfig {
      runtimeInventory = config.sinnix.runtime.inventory;
      unit = "sshd.service";
    };
    systemd.sockets.sshd.socketConfig = {
      Slice = config.sinnix.runtime.inventory.classes.interactive-access.serviceConfig.Slice;
    };

    # Bluetooth hardening handled by nixpkgs - it needs kernel module/tunable access
    systemd.services.bluetooth = lib.mkIf isDesktop {
      serviceConfig = lib.sinnix.systemd.mkRestartPolicy {
        strategy = "on-failure";
        delaySec = 3;
      };
    };

    hardware.bluetooth = lib.mkIf isDesktop {
      enable = lib.mkDefault true;
      powerOnBoot = lib.mkDefault true;
      package = lib.mkDefault pkgs.bluez;
      settings = {
        Policy = {
          AutoEnable = true;
          # Limit reconnection attempts for offline devices.
          # Default (7) with AVDTP retries causes 60+ attempts/hour to
          # powered-off headsets, flooding journal and dbus.
          ReconnectAttempts = lib.mkDefault 3;
        };
        General = {
          ControllerMode = lib.mkDefault "dual";
          DiscoverableTimeout = lib.mkDefault 0;
          Experimental = lib.mkDefault false;
          FastConnectable = lib.mkDefault true;
          MultiProfile = lib.mkDefault "multiple";
        };
      };
    };

    environment.systemPackages = lib.mkAfter (
      networkingToolPackages ++ lib.optionals isDesktop desktopNetworkingPackages
    );
  };
}
