# Core networking configuration
#
# Provides:
# - NetworkManager with systemd-resolved (DNSSEC allow-downgrade)
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
  bluezExperimental = pkgs.bluez.override { enableExperimental = true; };
  desktopNetworkingPackages = [
    pkgs.networkmanagerapplet
    bluezExperimental
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

    services = {
      # systemd-resolved provides local caching and .lan resolution.
      # Upstream DNS comes from DHCP (i.e., the router's dnsmasq which itself
      # forwards to Cloudflare DoH via https-dns-proxy).
      resolved = {
        enable = true;
        # Accept DHCP-provided DNS (the router). No static upstream overrides needed.
        settings = {
          Resolve = {
            # Router runs DoH (Cloudflare + Quad9) so DNSSEC validation is meaningful.
            # "allow-downgrade" validates when DNSSEC records exist, tolerates unsigned domains.
            DNSSEC = "allow-downgrade";
            # Resolve .lan names via the router's dnsmasq
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

    # sshd hardening handled by nixpkgs - custom seccomp filters break it
    systemd.services.sshd.serviceConfig = {
      Slice = "recovery.slice";
    };
    systemd.sockets.sshd.socketConfig = {
      Slice = "recovery.slice";
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
      package = lib.mkDefault bluezExperimental;
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
          Experimental = lib.mkDefault true;
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
