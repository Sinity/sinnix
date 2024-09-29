{ ... }: 
{
  security.rtkit.enable = true;
  security.sudo.wheelNeedsPassword = false;
  security.pam.services.hyprlock = {};
}
