{pkgs, ...}: {
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

  # For claude-desktop-with-fhs to run
  boot.kernel.sysctl."kernel.unprivileged_userns_clone" = 1;
  security.wrappers.bubblewrap = {
    source = "${pkgs.bubblewrap}/bin/bwrap";
    owner = "root";
    group = "root";
    setuid = true;
  };
}
