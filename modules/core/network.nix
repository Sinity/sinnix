{ pkgs, host, ... }: 
{
  networking = {
    hostName = "${host}";
    networkmanager.enable = true;
    networkmanager.insertNameservers = [ "1.1.1.1" "8.8.8.8" ];
    nameservers = [ "1.1.1.1#one.one.one.one" "8.8.8.8" ];
  };

  services = {
    resolved = {
      enable = true;
      dnssec = "allow-downgrade";
      domains = [ "~." ];
      fallbackDns = [ "1.1.1.1#one.one.one.one" "8.8.8.8" ];
      dnsovertls = "true";
    };

    openssh = {
      enable = true;
      startWhenNeeded = true;
      settings = {
        PermitRootLogin = "yes";
        PasswordAuthentication = true;
        LogLevel = "VERBOSE";
      };
    };

    mullvad-vpn = {
      enable = true;
      package = pkgs.mullvad-vpn;
    };
  };

  programs.mosh.enable = true;

  environment.systemPackages = with pkgs; [
    networkmanagerapplet
    mullvad-closest # benchmark latency to Mullvad relays
    # cloudflare-warp # Free VPN; "Replaces the connection between your device and the Internet with a modern, optimized, protocol"
  ];

  hardware = {
    bluetooth = {
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
  };
}
