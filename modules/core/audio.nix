{pkgs, ...}: {
  services.pulseaudio.enable = false;
  services.pipewire = {
    enable = true;
    audio.enable = true;
    alsa.enable = true;
    pulse.enable = true;
    jack.enable = true;

    extraConfig.pipewire."context.properties" = {
      "default.clock.rate" = 48000;
      "default.clock.quantum" = 64;
      "default.clock.min-quantum" = 32;
      "default.clock.max-quantum" = 128;
    };
  };

  environment.systemPackages = with pkgs; [
    pulseaudioFull
    alsa-utils
    pavucontrol
    pamixer
  ];

  security.rtkit.enable = true;
  systemd.user.services.pipewire.serviceConfig = {
    LimitMEMLOCK = "infinity";
    Nice = -11;
    CPUSchedulingPolicy = "fifo";
    CPUSchedulingPriority = 90;
  };

  security.pam.loginLimits = [
    {
      domain = "@audio";
      type = "hard";
      item = "memlock";
      value = "infinity";
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
