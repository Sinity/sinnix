{ ... }: 
{
  services = {
    gvfs.enable = true;
    gnome.gnome-keyring.enable = true;
    dbus.enable = true;
    fstrim.enable = true;
    openssh.enable = true;
  };

  services.journald = {
    extraConfig = ''
      SystemMaxUse=20G
      SystemKeepFree=10G
      SystemMaxFileSize=10M
      SystemMaxFiles=2500
      RuntimeMaxUse=1G
    '';
  };

  systemd.sleep = { # TODO: verify hibernation works
    extraConfig = ''
      AllowSuspend=yes
      AllowHibernation=yes
      AllowSuspendThenHibernate=yes
      AllowHybridSleep=yes
      HibernateMode=reboot
      HibernateState=disk
    '';
  };

  # To prevent getting stuck at shutdown
  systemd.extraConfig = "DefaultTimeoutStopSec=5s";

  # Monero configuration
  services.monero = {
    enable = true;
    dataDir = "/mnt/ssd_storage/monero";
    extraConfig = ''
      log-level=3
    '';
  };
}
