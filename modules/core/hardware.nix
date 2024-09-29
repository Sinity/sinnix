{ pkgs, ... }:
{
  hardware = {
    nvidia = {
      modesetting.enable = true;
      powerManagement.enable = false;
      powerManagement.finegrained = false;
      open = false;
      nvidiaSettings = true;
    };

    graphics = {
      enable = true;
      extraPackages = with pkgs; [
        edid-decode # for decoding EDID (display capabilities metadata, e.g. avaiable modes)
      ];
    };

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

  # make capslock key into escape key
  services.interception-tools = {
    enable = true;
    udevmonConfig = ''
      - JOB: "${pkgs.interception-tools}/bin/intercept -g $DEVNODE | ${pkgs.interception-tools-plugins.caps2esc}/bin/caps2esc -m 1 | ${pkgs.interception-tools}/bin/uinput -d $DEVNODE"
        DEVICE:
          EVENTS:
            EV_KEY: [KEY_CAPSLOCK, KEY_ESC]
    '';
  };

  # periodically TRIM ssd storage devices
  services.fstrim.enable = true;

  # set root partition options
  fileSystems."/".options = [ "strictatime" "lazytime" ];

  # setup mounts of storage at boot
  boot.supportedFilesystems = [ "btrfs" "ntfs" ];
  fileSystems."/mnt/ssd_storage" = {
    device = "/dev/disk/by-uuid/bd19092f-a195-47ab-9c0d-c923d1e5bfea";
    fsType = "btrfs";
    options = [
      "strictatime" "lazytime"
      "nofail"
    ];
  };
  fileSystems."/mnt/hdd_storage" = {
    device = "/dev/disk/by-uuid/5119B4113C747C42";
    fsType = "ntfs";
    options = [
      "strictatime" "lazytime"
      "nofail"
      "uid=1000" "gid=100" "umask=000"
      "big_writes"
    ];
  };
  fileSystems."/mnt/arch_root" = {
    device = "/dev/disk/by-uuid/481e214e-7bb6-49fa-bc87-ccb1f2c1e3c3";
    fsType = "ext4";
    options = [
      "strictatime" "lazytime"
      "nofail"
    ];
  };

  hardware.enableRedistributableFirmware = true;
}
