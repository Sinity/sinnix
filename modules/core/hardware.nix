{pkgs, intercept-bounce, ...}: { # Accept intercept-bounce as an argument
  # Use interception-tools with multiple filters
  services.interception-tools = {
    enable = true;
    udevmonConfig = ''
      # Job 1: intercept-bounce for a specific keyboard
      # This intercepts events from your keyboard device,
      # pipes them through the intercept-bounce filter with a 5ms window,
      # and then sends the filtered events to a new virtual device.
      - JOB: "${pkgs.interception-tools}/bin/intercept -g $DEVNODE \
            | ${intercept-bounce}/bin/intercept-bounce --window 5 \
            | ${pkgs.interception-tools}/bin/uinput -d $DEVNODE"
        DEVICE:
          # Logitech G915 Wireless Keyboard link
          LINK: "/dev/input/by-id/usb-Logitech_G915_WIRELESS_RGB_MECHANICAL_GAMING_KEYBOARD_87516961-event-kbd"

      # Job 2: caps2esc for any device sending CAPSLOCK
      # This intercepts CAPSLOCK events and transforms them into ESCAPE
      # when pressed alone, or CTRL when held with another key.
      - JOB: "${pkgs.interception-tools}/bin/intercept -g $DEVNODE \
            | ${pkgs.interception-tools-plugins.caps2esc}/bin/caps2esc \
            | ${pkgs.interception-tools}/bin/uinput -d $DEVNODE"
        DEVICE:
          # This job specifically targets the CAPSLOCK key event on any device.
          EVENTS:
            EV_KEY: [[KEY_CAPSLOCK]]
    '';
  };

  powerManagement.cpuFreqGovernor = "performance";
  hardware.enableRedistributableFirmware = true;
}
