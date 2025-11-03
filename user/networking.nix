{ pkgs, inputs, ... }:
let
  chromeStablePkg = inputs.browser-previews.packages.${pkgs.system}.google-chrome;
in
{
  home.sessionVariables.COMMUNICATION_DOMAIN = "v0.3";

  home.packages = [
    chromeStablePkg
  ]
  ++ (with pkgs; [
    qutebrowser
    tor-browser
    firefox
    weechat
    curl
    wget
    nmap
    dig
    traceroute
    whois
    netcat
    socat
    tcpdump
    mtr
    wireshark
    openssh
    mosh
  ]);

  programs.ssh = {
    enable = true;
    enableDefaultConfig = false;
    matchBlocks."*".addKeysToAgent = "yes";
  };
}
