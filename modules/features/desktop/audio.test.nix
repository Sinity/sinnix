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
        audioCapture = config.sinnix.features.desktop.audioCapture;
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
          assertion = builtins.any isXm4Rule xm4Rules;
          message = "WH-1000XM4 must be preferred as the default Bluetooth sink when it appears";
        }
        {
          assertion = audioCapture.captureOutputs == false;
          message = "Audio capture must not record output/sink monitors by default";
        }
        {
          assertion = audioCapture.captureAllInputs == false;
          message = "Audio capture must only record the preferred input by default";
        }
        {
          assertion = audioCapture.asrProvider == "local";
          message = "Audio capture must keep faster-whisper as the default until Cohere is explicitly enabled";
        }
        {
          assertion = audioCapture.cohereRevision == "refs/pr/6";
          message = "Audio capture must pin the working Cohere Transcribe model revision";
        }
        {
          assertion = builtins.elem audioCapture.asrProvider [
            "local"
            "cohere"
            "cohere-api"
          ];
          message = "Audio capture ASR providers must include local Cohere open-weights support";
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
