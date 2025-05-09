{pkgs, ...}: {
  services.pipewire = {
    enable = true;
    audio.enable = true;
    alsa.enable = true;
    pulse.enable = true;
    # jack.enable = true;

    # extraConfig.pipewire."context.properties" = {
    #   "default.clock.rate" = 48000;
    #   "default.clock.quantum" = 64;
    #   "default.clock.min-quantum" = 32;
    #   "default.clock.max-quantum" = 128;
    # };
  };

  environment.systemPackages = with pkgs; [
    pulseaudioFull
    alsa-utils
    pavucontrol
    pamixer
  ];

  systemd.user.services.pipewire.serviceConfig = {
    LimitRTPRIO = 95;
    LimitMEMLOCK = "infinity";
    Nice = -11;
    CPUSchedulingPolicy = "fifo";
    CPUSchedulingPriority = 90;
  };

  security.pam.loginLimits = [
    {
      domain = "@audio";
      type = "soft";
      item = "rtprio";
      value = "95";
    }
    {
      domain = "@audio";
      type = "hard";
      item = "rtprio";
      value = "95";
    }
    {
      domain = "@audio";
      type = "soft";
      item = "memlock";
      value = "unlimited";
    }
    {
      domain = "@audio";
      type = "hard";
      item = "memlock";
      value = "unlimited";
    }
  ];

  environment.etc."wireplumber/60-force-quantum.lua".text = ''
    rule = {
      matches = {
        { { "node.name", "matches", "alsa_output.usb-2cc2_*" }, },
      },
      apply_properties = { ["clock.force-quantum"] = 384 },
    }
    table.insert(alsa_monitor.rules, rule)
  '';
}
