{ pkgs, host, ... }: 
{
  networking = {
    hostName = "${host}";
    networkmanager.enable = true;
    nameservers = [ "1.1.1.1#one.one.one.one" "8.8.8.8" ];
    firewall.enable = false;
  };

  environment.systemPackages = with pkgs; [
    networkmanagerapplet
    # cloudflare-warp # Free VPN; "Replaces the connection between your device and the Internet with a modern, optimized, protocol"
    mullvad-closest # benchmark latency to Mullvad relays
  ];
  
  services.mullvad-vpn.enable = true;
  services.resolved = {
    enable = true;
    dnssec = "allow-downgrade";
    domains = [ "~." ];
    fallbackDns = [ "1.1.1.1#one.one.one.one" "8.8.8.8" ];
    dnsovertls = "true";
  };
}
