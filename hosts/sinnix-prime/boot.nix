# Host-specific boot configuration for sinnix-prime
{ pkgs, ... }:
{
  boot = {
    loader = {
      systemd-boot = {
        enable = true;
        configurationLimit = null;
      };
      efi.canTouchEfiVariables = true;
    };

    # Switch to the bleeding-edge kernel set so we pick up the
    # 6.13 tree, which includes the upstream fix for the NVMe/ext4
    # writeback soft-lockups we've been hitting.
    kernelPackages = pkgs.linuxPackages_testing;

    initrd.availableKernelModules = [
      "xhci_pci"
      "ahci"
      "nvme"
      "usbhid"
      "usb_storage"
      "sd_mod"
    ];
    blacklistedKernelModules = [
      "i915"
      # Removing SOF/AVS blacklist to test if it helps with binding
      # "snd_sof_pci_intel_tgl"
      # "snd_sof_intel_hda_common"
      # "snd_sof_intel_hda"
      # "snd_sof_pci"
      # "snd_sof"
      # "snd_soc_avs"
    ];
    kernelModules = [ "kvm-intel" ];
    kernel.sysctl = {
      "vm.swappiness" = 10;
      # Flush dirty pages earlier to avoid the huge writeback spikes
      # that were triggering the kernel spin-lock regression on 6.12.x.
      "vm.dirty_ratio" = 10;
      "vm.dirty_background_ratio" = 5;
    };
    kernelParams = [
      "quiet"
      "rw"
      "vconsole.keymap=pl"
      "vconsole.font=Lat2-Terminus16"
      "vconsole.font_map=8859-2"
      "vt.global_cursor_default=0"
      "loglevel=3"
      "rd.systemd.show_status=false"
      "rd.udev.log-priority=3"
      "acpi_enforce_resources=lax"
      "vga=current"
    ];
  };
}
