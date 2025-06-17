# Virtual Machine Scripts
# Scripts for managing VMs and system-level utilities

{ pkgs, ... }:
let
  vm-start = pkgs.writeShellScriptBin "vm-start" ''
    # VM name
    vm_name="win10"
    export LIBVIRT_DEFAULT_URI="qemu:///system"

    # change workspace
    ${pkgs.hyprland}/bin/hyprctl dispatch workspace 6

    ${pkgs.libvirt}/bin/virsh start "$vm_name"
    ${pkgs.virt-viewer}/bin/virt-viewer -f -w -a "$vm_name"
  '';

in
{
  config = {
    environment.systemPackages = [
      vm-start
    ];
  };
}
