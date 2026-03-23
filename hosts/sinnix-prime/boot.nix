# Host-specific boot configuration for sinnix-prime
{
  pkgs,
  lib,
  config,
  ...
}:
{
  boot = {
    loader = {
      systemd-boot = {
        enable = true;
        # Keep only the recent experiment window in the boot menu.
        # With the current generation at 336, 22 entries keeps >=315 and drops the
        # stale UKI/BLS clutter from the earlier bring-up churn.
        configurationLimit = 22;
        extraInstallCommands = ''
          loader_conf="${config.boot.loader.efi.efiSysMountPoint}/loader/loader.conf"
          default_entry="$(${pkgs.gawk}/bin/awk '$1 == "default" { print $2; exit }' "$loader_conf")"

          if [[ -n "$default_entry" ]]; then
            ${config.systemd.package}/bin/bootctl set-default "$default_entry"
          fi
        '';
      };
      efi.canTouchEfiVariables = true;
    };

    kernelPackages = pkgs.linuxPackages;

    initrd.availableKernelModules = [
      "xhci_pci"
      "ahci"
      "nvme"
      "usbhid"
      "usb_storage"
      "sd_mod"
    ];

    # i915 blacklisted for pure-NVIDIA modes to prevent KMS init conflicts.
    # igpu: i915 handles UHD 770 (no xe in play without nvidia).
    # dual: xe loads as nvidia's transitive dep and claims the iGPU PCI ID first;
    #       xe.force_probe=a780 (below) makes it actually bind. i915 not needed.
    # Controlled by sinnix.gpu.mode — do not edit manually.
    # nouveau auto-probes any NVIDIA device it finds; on igpu mode the RTX 3080
    # is still physically on the PCIe bus, and nouveau + GA102 Ampere (GSP path)
    # is unstable enough to hard-reset the system. Blacklist it explicitly.
    blacklistedKernelModules =
      lib.optionals (config.sinnix.gpu.mode == "nvidia" || config.sinnix.gpu.mode == "nvidia-open") [
        "i915"
      ]
      ++ lib.optionals (config.sinnix.gpu.mode == "igpu") [ "nouveau" ];
    kernelModules = [ "kvm-intel" ] ++ lib.optionals (config.sinnix.gpu.mode == "igpu") [ "i915" ];

    consoleLogLevel = 3;

    kernelParams = [
      "quiet"
      "rw"
      "vconsole.keymap=pl"
      "vconsole.font=Lat2-Terminus16"
      "vconsole.font_map=8859-2"
      "vt.global_cursor_default=0"
      "rd.systemd.show_status=false"
      "rd.udev.log-priority=3"
      "acpi_enforce_resources=lax"
      "vga=current"
    ]
    ++ lib.optionals (config.sinnix.gpu.mode == "dual") [
      # xe loads as a transitive dep of nvidia and claims the iGPU PCI ID (0xa780)
      # before i915 can bind. force_probe opts the UHD 770 into xe's binding path.
      "xe.force_probe=a780"
    ];
  };

  hardware.enableRedistributableFirmware = true;
}
