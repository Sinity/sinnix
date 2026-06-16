{
  mountTmpfsRoots,
  baseTestConfig,
  mkFeatureTest,
  ...
}:
[
  (mkFeatureTest {
    name = "desktop-audio";
    feature = "sinnix.features.desktop.audio.enable";
    assertions =
      config:
      let
        wireplumber = config.services.pipewire.wireplumber.extraConfig;
        bluezRoles = wireplumber."10-bluez"."monitor.bluez.properties"."bluez5.roles" or [ ];
        xm4Rules = wireplumber."12-preferred-xm4-output"."monitor.bluez.rules" or [ ];
        isXm4Rule =
          rule:
          (builtins.elemAt (rule.matches or [ ]) 0)."node.name" or null
          == "~bluez_output.*AC_80_0A_D4_08_48.*"
          && (rule.actions.update-props."priority.session" or null) == 2100
          && (rule.actions.update-props."priority.driver" or null) == 2100;
      in
      [
        {
          assertion = config.services.pipewire.enable or false;
          message = "Desktop audio must enable PipeWire";
        }
        {
          assertion = config.services.pipewire.wireplumber.enable or false;
          message = "Desktop audio must enable WirePlumber";
        }
        {
          assertion = config.systemd.user.services.wireplumber.serviceConfig.Restart == "always";
          message = "WirePlumber must restart after clean exits so Bluetooth A2DP endpoints return";
        }
        {
          assertion = builtins.any isXm4Rule xm4Rules;
          message = "WH-1000XM4 must be preferred as the default Bluetooth sink when it appears";
        }
        {
          assertion = !(builtins.elem "bap_sink" bluezRoles) && !(builtins.elem "bap_source" bluezRoles);
          message = "Bluetooth audio must not expose unstable LE Audio/BAP roles";
        }
      ];
  })
  {
    name = "desktop-bluetooth-persistence";
    modules = [
      mountTmpfsRoots
      baseTestConfig
      (
        { ... }:
        {
          networking.hostName = "desktop-bluetooth-persistence";
          sinnix.machine.isDesktop = true;
          sinnix.persistence.enable = true;
        }
      )
    ];
    assertions =
      config:
      let
        isBluetoothDir =
          entry:
          if builtins.isAttrs entry then
            (entry.directory or null) == "/var/lib/bluetooth"
          else
            entry == "/var/lib/bluetooth";
      in
      [
        {
          assertion = config.hardware.bluetooth.enable or false;
          message = "Desktop hosts must enable Bluetooth support";
        }
        {
          assertion = builtins.any isBluetoothDir config.sinnix.persistence.system.directories;
          message = "Bluetooth state must be persisted under /var/lib/bluetooth";
        }
      ];
  }
]
