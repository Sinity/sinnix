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
	  # FastConnectable = true;
	};

	Policy = {
	  AutoEnable = true;
	};
      };
    };
  };
  hardware.enableRedistributableFirmware = true;
}
