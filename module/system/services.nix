_: {
  # To prevent getting stuck at shutdown
  systemd.extraConfig = "DefaultTimeoutStopSec=5s";
  systemd.sleep = {
    # TODO: verify hibernation works
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
        SystemMaxUse=50G
        SystemKeepFree=25G
        SystemMaxFileSize=10M
        SystemMaxFiles=5000000
        RuntimeMaxUse=2G
      '';
    };

    # monero = {
    #   enable = true;
    #   dataDir = "/realm/monero/";
    #   extraConfig = "log-level=3";
    # };

    transmission = {
      enable = true;
      settings = {
        script-torrent-done-enabled = false;
        ratio-limit-enabled = false;
        umask = 18; # 002
        download-dir = "/outer-realm/inbox";
        incomplete-dir-enabled = false;
        rpc-port = 9091;
        # rpc-url = "/transmission/";
      };
    };

    ollama = {
      enable = true;
      acceleration = "cuda";
    };
  };
}
