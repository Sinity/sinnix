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
        connectionConfig = {
          "ipv4.ignore-auto-dns" = true;
          "ipv6.ignore-auto-dns" = true;
          "ipv4.dns" = "1.1.1.1;8.8.8.8;";
          "ipv6.dns" = "2606:4700:4700::1111;2001:4860:4860::8888;";
        };
      };
    };

    services = {
      resolved = {
        enable = true;
        dnssec = "allow-downgrade";
        domains = [ "~." ];
        dnsovertls = "opportunistic";
        fallbackDns = [
          "1.0.0.1#one.one.one.one"
          "8.8.4.4#dns.google"
          "2606:4700:4700::1001#one.one.one.one"
          "2001:4860:4860::8844#dns.google"
        ];
        extraConfig = ''
          DNS=1.1.1.1#one.one.one.one 8.8.8.8#dns.google 2606:4700:4700::1111#one.one.one.one 2001:4860:4860::8888#dns.google
          FallbackDNS=1.0.0.1#one.one.one.one 8.8.4.4#dns.google 2606:4700:4700::1001#one.one.one.one 2001:4860:4860::8844#dns.google
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
        };
      };

    };

    programs.mosh.enable = true;

    systemd.services.sshd.serviceConfig = {
      Slice = "recovery.slice";
    };
    systemd.sockets.sshd.socketConfig = {
      Slice = "recovery.slice";
    };

    hardware.bluetooth = lib.mkIf isDesktop {
      enable = lib.mkDefault true;
      powerOnBoot = lib.mkDefault true;
      package = lib.mkDefault bluezExperimental;
      settings = {
        Policy.AutoEnable = true;
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
