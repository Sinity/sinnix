# Communication Domain Module
# Complete connectivity (network + apps)
# Consolidates: network config, browsers, servers, messaging, email

{
  config,
  lib,
  pkgs,
  username,
  host,
  inputs,
  ...
}:
with lib;
{
  config = mkMerge [
    # System-level communication configuration
    {
      # Domain identification
      system.nixos.tags = [ "communication-domain-v0.3" ];

      # Network configuration
      networking = {
        hostName = "${host}";
        networkmanager.enable = true;
        networkmanager.insertNameservers = [
          "1.1.1.1"
          "8.8.8.8"
        ];
        nameservers = [
          "1.1.1.1#one.one.one.one"
          "8.8.8.8"
        ];
      };

      # Services configuration
      services = {
        # DNS-over-TLS
        resolved = {
          enable = true;
          dnssec = "allow-downgrade";
          domains = [ "~." ];
          fallbackDns = [
            "1.1.1.1#one.one.one.one"
            "8.8.8.8"
          ];
          dnsovertls = "true";
        };

        # SSH server
        openssh = {
          enable = true;
          startWhenNeeded = false;
          ports = [ 22 ];
          settings = {
            PermitRootLogin = "yes";
            PasswordAuthentication = true;
            LogLevel = "VERBOSE";
          };
        };

        # Web server
        nginx = {
          enable = true;
          virtualHosts."_" = {
            listen = [
              {
                addr = "0.0.0.0";
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

      # Create web directory
      system.activationScripts = {
        createWebDir = {
          text = ''
            mkdir -p /var/www/simple-site
            chown -R nginx:nginx /var/www/simple-site
          '';
          deps = [ ];
        };
      };

      # Mobile shell support
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
    }

    # User-level communication configuration
    {
      home-manager.users.${username} = {
        # Communication environment variables
        home = {
          sessionVariables = {
            COMMUNICATION_DOMAIN = "v0.3";
            # Default browser is set via XDG mime associations
          };

          # Communication packages
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
            wireshark

            # SSH/Remote tools
            openssh
            mosh
            # remmina # Remote desktop client
          ];
        };

        # SSH client configuration
        programs.ssh = {
          enable = true;
          addKeysToAgent = "yes";
          package = pkgs.openssh;

          # # SSH match blocks can be configured here
          # matchBlocks = {
          #   "*" = {
          #     ForwardAgent = "no";
          #     ServerAliveInterval = 0;
          #     ServerAliveCountMax = 3;
          #     HashKnownHosts = "no";
          #     UserKnownHostsFile = "~/.ssh/known_hosts";
          #     ControlMaster = "no";
          #     ControlPath = "~/.ssh/master-%r@%n:%p";
          #     ControlPersist = "no";
          #     IdentitiesOnly = "yes";
          #   };
          # };
        };

        # Browser configuration is handled via XDG in interface domain (xdg-mimes.nix)
      };
    }
  ];
}
