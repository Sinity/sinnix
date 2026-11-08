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
  operator = config.sinnix.user.name;
in
{
  options.sinnix.networking.enable = lib.mkOption {
    type = lib.types.bool;
    default = true;
    description = "Enable core networking configuration (NetworkManager, DNS, SSH)";
  };

  options.sinnix.networking.operatorOnlyLocalPorts = lib.mkOption {
    type = lib.types.listOf lib.types.port;
    default = [ ];
    description = ''
      TCP ports that local processes may connect to only as the operator (or
      root). Listeners such as Chrome's remote-debugging port and the hub
      authorize every caller who can reach them, so a connection from any
      other local account is refused before it reaches the socket.
    '';
  };

  config = lib.mkIf cfg.enable {
    networking.firewall = lib.mkIf (cfg.operatorOnlyLocalPorts != [ ]) {
      # Locally generated connections pass OUTPUT; the owner match sees the
      # connecting account. The chain is rebuilt on every firewall reload.
      extraCommands = ''
        ip46tables -N sinnix-operator-only 2>/dev/null || true
        ip46tables -F sinnix-operator-only
        ip46tables -C OUTPUT -j sinnix-operator-only 2>/dev/null || ip46tables -I OUTPUT -j sinnix-operator-only
        ${lib.concatMapStrings (port: ''
          ip46tables -A sinnix-operator-only -p tcp --dport ${toString port} -m owner --uid-owner ${operator} -j RETURN
          ip46tables -A sinnix-operator-only -p tcp --dport ${toString port} -m owner --uid-owner 0 -j RETURN
          ip46tables -A sinnix-operator-only -p tcp --dport ${toString port} -m owner --uid-owner 1-4294967294 -j REJECT --reject-with tcp-reset
        '') cfg.operatorOnlyLocalPorts}
      '';
      extraStopCommands = ''
        ip46tables -D OUTPUT -j sinnix-operator-only 2>/dev/null || true
        ip46tables -F sinnix-operator-only 2>/dev/null || true
        ip46tables -X sinnix-operator-only 2>/dev/null || true
      '';
    };

    networking = {
      networkmanager = {
        enable = true;
        dns = "systemd-resolved";
        # DNS authority is the router (sinnix-gw), which runs https-dns-proxy
        # → Cloudflare DoH and advertises itself over DHCP.
      };
    };

    # network-online.target must mean a working connection: Transmission and
    # the GitHub runner order on it, and with this unit disabled both started
    # before DNS answered. Upstream's `nm-online -s` waits for every
    # autoconnect profile to settle, so one slow profile failed the unit;
    # plain `nm-online` returns once any connection is up. Units that need
    # the network start from sinnix-background.target, so this wait never
    # delays the desktop.
    systemd.services.NetworkManager-wait-online.serviceConfig.ExecStart = [
      ""
      "${config.networking.networkmanager.package}/bin/nm-online -q"
    ];

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
    systemd.services.sshd.serviceConfig =
      (lib.sinnix.mkRuntimeServiceConfig {
        runtimeInventory = config.sinnix.runtime.inventory;
        unit = "sshd.service";
      })
      // {
        # Remote access is the recovery path when the graphical session or a
        # runaway user workload makes local input unusable. This survives the
        # PAM move into a login scope because the adjustment is inherited by
        # sshd's children; the system-critical slice already supplies the CPU,
        # IO, and 2 GiB MemoryLow protection for accepting the connection.
        OOMScoreAdjust = -900;
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
