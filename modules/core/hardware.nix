{
  pkgs,
  intercept-bounce,
  ...
}: {
  environment.systemPackages = with pkgs; [intercept-bounce interception-tools interception-tools-plugins.caps2esc];
  services.interception-tools = {
    enable = true;

    udevmonConfig = ''
      # Job: Apply debouncing, then caps2esc, for all keyboards
      - JOB: "${pkgs.interception-tools}/bin/intercept -g $DEVNODE \
            | ${intercept-bounce}/bin/intercept-bounce -t 25 --log-interval 60 --log-bounces --stats-json \
            | ${pkgs.interception-tools-plugins.caps2esc}/bin/caps2esc \
            | ${pkgs.interception-tools}/bin/uinput -d $DEVNODE"
        DEVICE:
          # Match devices capable of emitting EV_KEY events
          CAPABILITIES:
            EV: [EV_KEY]
    '';
  };

  powerManagement.cpuFreqGovernor = "performance";
  hardware.enableRedistributableFirmware = true;
}
