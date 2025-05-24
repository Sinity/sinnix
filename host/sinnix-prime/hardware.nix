# Host-specific hardware configuration for sinnix-prime
{ pkgs, intercept-bounce, ... }:
{
  environment.systemPackages = with pkgs; [
    intercept-bounce
    interception-tools
    interception-tools-plugins.caps2esc
  ];
  services.interception-tools = {
    enable = true;
    udevmonConfig = ''
      - JOB: "${pkgs.interception-tools}/bin/intercept -g $DEVNODE \
            | ${intercept-bounce}/bin/intercept-bounce -t 40ms --log-interval 6h --log-bounces --stats-json \
            | ${pkgs.interception-tools-plugins.caps2esc}/bin/caps2esc -m 1 \
            | ${pkgs.interception-tools}/bin/uinput -d $DEVNODE"
        DEVICE:
          LINK: "/dev/input/by-id/usb-Logitech_USB_Receiver-if01-event-kbd"
    '';
  };

  powerManagement.cpuFreqGovernor = "performance";
  hardware.enableRedistributableFirmware = true;
}
