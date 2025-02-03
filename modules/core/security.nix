{ ... }: 
{
  security.rtkit.enable = true;
  security.sudo.wheelNeedsPassword = false;
  security.pam.services.hyprlock = {};
  networking.firewall.enable = false;

  services.gnome.gnome-keyring.enable = true;
  programs.gnupg.agent = {
    enable = true;
    enableSSHSupport = true;
    # pinentryFlavor = "";
  };
}
