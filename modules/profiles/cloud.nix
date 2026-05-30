# Cloud / headless host profile.
#
# Coarse aggregate for headless cloud or dedicated-server boxes (Hetzner AX,
# VPS). Sets `sinnix.machine.isDesktop = false` and the matching networking,
# console, and firewall posture. Per-host configs still pick the actual
# services (sinex role, tailscale tags, backups, etc.).
#
# Inert until explicitly enabled per host. Prime keeps `isDesktop = true`
# and never imports this.
{
  config,
  lib,
  ...
}:
let
  cfg = config.sinnix.profiles.cloud;
in
{
  options.sinnix.profiles.cloud.enable = lib.mkEnableOption "Headless cloud-host profile";

  config = lib.mkIf cfg.enable {
    sinnix.machine.isDesktop = lib.mkForce false;

    # Headless boxes use systemd-networkd; NetworkManager is a desktop tool.
    networking = {
      useNetworkd = true;
      networkmanager.enable = lib.mkForce false;
      firewall = {
        allowedTCPPorts = lib.mkForce [ 22 ];
        # Tailscale opens its own UDP port via services.tailscale.openFirewall.
        trustedInterfaces = [ "tailscale0" ];
      };
    };

    # Serial console on ttyS0 plus VGA, so KVM/IPMI and remote-hands both work.
    boot.kernelParams = [
      "console=ttyS0,115200n8"
      "console=tty1"
    ];
    systemd.services."serial-getty@ttyS0".enable = true;

    # Bare-metal dedicated server: not a QEMU guest. Per-host configs that run
    # in a VM (e.g. a future sinnix-vps) can re-enable explicitly.
    services.qemuGuest.enable = lib.mkForce false;

    # Desktop graphical stack is off via isDesktop, but be explicit for hosts
    # that import desktop modules unconditionally.
    services.xserver.enable = lib.mkForce false;
  };
}
