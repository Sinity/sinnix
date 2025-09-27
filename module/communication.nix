# Communication Domain Module
# Complete connectivity (network + apps)
# Consolidates: network config, browsers, servers, messaging, email

{
  pkgs,
  host,
  inputs,
  ...
}:
{
  system.nixos.tags = [ "communication-domain-v0.3" ];

  networking = {
    hostName = "${host}";
    networkmanager = {
      enable = true;
      dns = "systemd-resolved";
      settings.connection = {
        "ipv4.ignore-auto-dns" = true;
        "ipv6.ignore-auto-dns" = true;
        "ipv4.dns" = "1.1.1.1;8.8.8.8;";
        "ipv6.dns" = "2606:4700:4700::1111;2001:4860:4860::8888;";
      };
    };
  };

  services = {
    # DNS-over-TLS
    resolved = {
      enable = true;
      dnssec = "allow-downgrade";
      domains = [ "~." ];
      dnsovertls = "true";
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
        PermitRootLogin = "no";
        PasswordAuthentication = false;
        KbdInteractiveAuthentication = false;
        LogLevel = "VERBOSE";
      };
    };

    nginx = {
      enable = true;
      virtualHosts."_" = {
        listen = [
          {
            addr = "127.0.0.1";
            port = 80;
          }
        ];
        root = "/var/www/simple-site";
      };
    };

    # VPN configuration (commented for now)
    # mullvad-vpn = {
    #   enable = true;
    #   package = pkgs.mullvad-vpn;
    # };
  };

  # Ensure web root exists with correct ownership
  systemd.tmpfiles.rules = [
    "d /var/www/simple-site 0750 nginx nginx -"
  ];

  programs.mosh.enable = true;

  # Bluetooth configuration
  hardware.bluetooth = {
    enable = true;
    settings = {
      General = {
        Name = "Sinity-PC-BT";
        DiscoverableTimeout = 0;
        AlwaysPairable = true;
        PairableTimeout = 0;
        FastConnectable = true;
      };
      Policy = {
        AutoEnable = true;
      };
    };
  };

  # System communication packages
  environment.systemPackages = with pkgs; [
    networkmanagerapplet
    bluez
    bluez-tools
    # mullvad-closest # benchmark latency to Mullvad relays
    # cloudflare-warp # Free VPN
  ];

  # Firewall is disabled in security.nix - consider moving here
  # networking.firewall.enable = false;

  home-manager.users.sinity = {
    home = {
      sessionVariables = {
        COMMUNICATION_DOMAIN = "v0.3";
        # Default browser is set via XDG mime associations
      };

      packages = with pkgs; [
        # Web browsers
        inputs.browser-previews.packages.${pkgs.system}.google-chrome-beta
        inputs.browser-previews.packages.${pkgs.system}.google-chrome-dev
        qutebrowser
        tor-browser-bundle-bin
        firefox
        # chromium

        # Communication tools
        weechat # IRC client
        # discord
        # slack
        # telegram-desktop
        # signal-desktop
        # element-desktop # Matrix client
        # thunderbird # Email client
        # zoom-us
        # teams

        # Network tools
        curl
        wget
        nmap
        dig
        traceroute
        whois
        netcat
        socat
        tcpdump
        mtr # Network diagnostic tool
        wireshark

        # SSH/Remote tools
        openssh
        mosh
        # remmina # Remote desktop client
      ];
    };

    programs.ssh = {
      enable = true;
      enableDefaultConfig = false;
      matchBlocks = {
        "*" = {
          addKeysToAgent = "yes";
        };
      };
    };
  };
}
