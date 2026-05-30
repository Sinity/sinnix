# sinnix-ethereal boot: Hetzner AX42 (bare metal, UEFI).
#
# Modern Hetzner dedicated supports UEFI; use systemd-boot on the ESP that
# disko.nix provisions at /boot. Serial console kernel params come from the
# cloud profile (modules/profiles/cloud.nix).
{ pkgs, lib, ... }:
{
  boot = {
    loader = {
      systemd-boot = {
        enable = true;
        configurationLimit = 10;
      };
      efi.canTouchEfiVariables = true;
      timeout = 5;
      # The shared boot module assumes prime's mirrored-boot layout; force
      # it empty here since ethereal has a single ESP.
      grub.mirroredBoots = lib.mkForce [ ];
      grub.enable = lib.mkForce false;
    };

    kernelPackages = pkgs.linuxPackages;

    # `boot.shell_on_fail` is an emergency-only convenience for a headless
    # box where a wedged initrd is otherwise unrecoverable without IPMI.
    kernelParams = [ "boot.shell_on_fail" ];
  };
}
