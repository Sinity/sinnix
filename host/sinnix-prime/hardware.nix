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
        # - JOB: "${pkgs.interception-tools}/bin/intercept -g $DEVNODE \
        #       | ${intercept-bounce}/bin/intercept-bounce -t 25 --log-interval 60 --log-bounces --stats-json \
        #       | ${pkgs.interception-tools}/bin/uinput -d $DEVNODE"
        #   DEVICE:
        #     LINK: "/dev/input/by-id/usb-Logitech_G915_WIRELESS_RGB_MECHANICAL_GAMING_KEYBOARD_87516961-event-kbd"

        - JOB: "${pkgs.interception-tools}/bin/intercept -g $DEVNODE \
              | ${intercept-bounce}/bin/intercept-bounce -t 40ms --log-interval 6h --log-bounces --stats-json \
              | ${pkgs.interception-tools-plugins.caps2esc}/bin/caps2esc -m 1 \
              | ${pkgs.interception-tools}/bin/uinput -d $DEVNODE"
          DEVICE:
            LINK: "/dev/input/by-id/usb-Logitech_USB_Receiver-if01-event-kbd"
            # LINK: "/dev/input/by-id/usb-Logitech_G915_WIRELESS_RGB_MECHANICAL_GAMING_KEYBOARD_87516961-event-kbd" # wiredt stats-json

      #   - JOB: "${pkgs.interception-tools}/bin/intercept -g $DEVNODE \
      #         | ${pkgs.interception-tools-plugins.caps2esc}/bin/caps2esc \
      #         | ${pkgs.interception-tools}/bin/uinput -d $DEVNODE"
      #     DEVICE:
      #       # This job specifically targets the CAPSLOCK key event on any device.
      #       EVENTS:
      #         EV_KEY: [[KEY_CAPSLOCK]]
      #
      # - JOB: "${pkgs.interception-tools}/bin/intercept -g $DEVNODE \
      #       | ${intercept-bounce}/bin/intercept-bounce -t 25 --log-interval 60 --log-bounces --stats-json \
      #       | ${pkgs.interception-tools-plugins.caps2esc}/bin/caps2esc \
      #       | ${pkgs.interception-tools}/bin/uinput -d $DEVNODE"
      #   DEVICE:
      #     # Match devices capable of emitting EV_KEY events
      #     CAPABILITIES:
      #       EV: [EV_KEY]
    '';
  };

  powerManagement.cpuFreqGovernor = "performance";
  hardware.enableRedistributableFirmware = true;
}
