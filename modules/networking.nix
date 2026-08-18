# Core networking configuration
#
# NetworkManager plus a systemd-resolved stub, DNS and NTP pointed at the
# router (sinnix-gw), hardened OpenSSH, mosh, and desktop Bluetooth.
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
        # DNS authority is the router (sinnix-gw), which runs https-dns-proxy
        # → Cloudflare DoH and advertises itself over DHCP.
      };
    };

    # nm-online -s waits for every autoconnect profile to settle or time out
    # (60s); a cold-boot WPA handshake or DHCP renewal regularly trips that,
    # leaving a failed unit. Nothing on a desktop depends on it.
    systemd.services.NetworkManager-wait-online.enable = false;

    services = {
      # Local stub resolver and .lan handling only; the router stays the DNS
      # authority and forwards upstream via DoH.
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
            # LAN name-spoofing surface (listens on 0.0.0.0:5355) with no
            # legitimate use here: DNS is router-authoritative and .lan is
            # served by dnsmasq.
            LLMNR = false;
            # Resolve .lan names via the router's dnsmasq.
            Domains = [ "~lan" ];
          };
        };
      };

      # The router syncs upstream via ntpd; using it keeps LAN time consistent.
      timesyncd = {
        enable = true;
        servers = [ "192.168.1.1" ];
        settings.Time.FallbackNTP = "0.nixos.pool.ntp.org 1.nixos.pool.ntp.org";
      };

      openssh = {
        enable = true;
        settings = {
          UseDns = false;
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
          # The default (7) combined with AVDTP retries produces dozens of
          # reconnect attempts an hour to powered-off devices, flooding the
          # journal and dbus.
          ReconnectAttempts = lib.mkDefault 3;
        };
        General = {
          ControllerMode = lib.mkDefault "dual";
          DiscoverableTimeout = lib.mkDefault 0;
          # Enables bluez's experimental D-Bus interfaces, in particular
          # org.bluez.Battery1 -- without it, paired devices that report
          # battery over GATT (0x180f) or HFP AT-commands are invisible to
          # both upower and this host's own capture-peripherals bt-battery
          # lane (modules/services/capture-peripherals.nix).
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
