{
  lib,
  pkgs,
  ...
}:
{
  services.pipewire = {
    enable = true;
    audio.enable = true;
    alsa.enable = true;
    pulse.enable = true;
    wireplumber = {
      enable = true;
      extraConfig = {
        "11-bluetooth-policy"."wireplumber.settings"."bluetooth.autoswitch-to-headset-profile" = false;
        "10-bluez"."monitor.bluez.properties" = {
          "bluez5.enable-sbc-xq" = true;
          "bluez5.enable-msbc" = true;
          "bluez5.enable-hw-volume" = true;
          "bluez5.roles" = [
            "a2dp_sink"
            "a2dp_source"
          ];
        };
      };
    };
  };

  systemd.user.services.pipewire.serviceConfig = {
    LimitRTPRIO = 95;
    LimitMEMLOCK = "infinity";
    Nice = -11;
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

  environment.systemPackages = with pkgs; [
    alsa-utils
    pavucontrol
    pamixer
    bluez
    playerctl
  ];

  users.users.sinity.extraGroups = lib.mkAfter [
    "audio"
    "bluetooth"
  ];

  systemd.tmpfiles.rules = lib.mkAfter [
    "d /realm/home/.hydrus 0750 sinity users -"
    "d /realm/home/.hydrus/db 0750 sinity users -"
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
