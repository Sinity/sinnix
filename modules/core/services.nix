{ ... }: 
{
  # To prevent getting stuck at shutdown
  systemd.extraConfig = "DefaultTimeoutStopSec=5s";
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

  services = {
    journald = {
      extraConfig = ''
        SystemMaxUse=20G
        SystemKeepFree=10G
        SystemMaxFileSize=10M
        SystemMaxFiles=2500
        RuntimeMaxUse=1G
      '';
    };

    monero = {
      enable = true;
      dataDir = "/mnt/ssd_storage/monero";
      extraConfig = "log-level=3";
    };

    transmission = {
      enable = true;
      settings = {
        script-torrent-done-enabled = false;
        ratio-limit-enabled = false;
        umask = 18; # 002
        download-dir = "/mnt/hdd_storage/inbox";
        incomplete-dir-enabled = false;
        rpc-port = 9091;
        # rpc-url = "/transmission/";
      };
    };
  };
}
