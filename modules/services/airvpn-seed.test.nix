{ mkServiceTest, ... }:
let
  commonAssertions =
    config:
    let
      wg = config.networking.wireguard.interfaces.airvpn-seed;
      peer = builtins.head wg.peers;
      transmissionAfter = config.systemd.services.transmission.after or [ ];
      transmissionWants = config.systemd.services.transmission.wants or [ ];
      transmissionPartOf = config.systemd.services.transmission.unitConfig.PartOf or [ ];
      transmissionBindsTo = config.systemd.services.transmission.unitConfig.BindsTo or [ ];
    in
    [
      {
        assertion = wg.allowedIPsAsRoutes == false;
        message = "airvpn-seed must suppress automatic main-table routes";
      }
      {
        assertion = peer.allowedIPs == [ "0.0.0.0/0" ];
        message = "airvpn-seed peer must keep full-tunnel allowed IPs";
      }
      {
        assertion =
          builtins.elem "wireguard-airvpn-seed.target" transmissionAfter
          && builtins.elem "wireguard-airvpn-seed.target" transmissionWants;
        message = "Transmission must start the complete AirVPN WireGuard target";
      }
      {
        assertion =
          builtins.elem "wireguard-airvpn-seed.target" transmissionPartOf
          && builtins.elem "wireguard-airvpn-seed.target" transmissionBindsTo;
        message = "Transmission must restart with the complete AirVPN WireGuard target";
      }
      {
        assertion = config.sinnix.services.airvpn-seed.health.unit == "wireguard-airvpn-seed.service";
        message = "airvpn-seed health must reference the generated WireGuard unit";
      }
    ];
in
[
  (mkServiceTest {
    name = "services-airvpn-seed";
    service = "airvpn-seed";
    assertions =
      config:
      commonAssertions config
      ++ [
        {
          assertion = builtins.elem "multi-user.target" (
            config.systemd.targets.wireguard-airvpn-seed.wantedBy or [ ]
          );
          message = "airvpn-seed must start at boot by default";
        }
      ];
  })
  (mkServiceTest {
    name = "services-airvpn-seed-manual-start";
    service = "airvpn-seed";
    extraModules = [
      {
        sinnix.services.airvpn-seed.autoStart = false;
      }
    ];
    assertions =
      config:
      commonAssertions config
      ++ [
        {
          assertion = config.systemd.targets.wireguard-airvpn-seed.wantedBy == [ ];
          message = "airvpn-seed autoStart=false must remove boot target installation";
        }
      ];
  })
]
