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
      timeout = 15;
      systemd-boot = {
        editor = true;
        consoleMode = "keep";
        enable = true;
        memtest86.enable = true;
        edk2-uefi-shell.enable = true;
        # Keep the boot menu readable and leave the deeper rollback window to
        # the Nix profile itself.
        configurationLimit = 10;
        extraInstallCommands = ''
          loader_conf="${config.boot.loader.efi.efiSysMountPoint}/loader/loader.conf"
          default_entry="$(${pkgs.gawk}/bin/awk '$1 == "default" { print $2; exit }' "$loader_conf")"

          if [[ -n "$default_entry" ]]; then
            ${config.systemd.package}/bin/bootctl set-default "$default_entry"
          fi

          for entry in "${config.boot.loader.efi.efiSysMountPoint}"/loader/entries/nixos-generation-*.conf; do
            [[ -e "$entry" ]] || continue

            version_line="$(${pkgs.gawk}/bin/awk '$1 == "version" { sub(/^version[ \t]+/, ""); print; exit }' "$entry")"
            generation="$(${pkgs.gawk}/bin/awk '$1 == "version" { print $3; exit }' "$entry")"
            kernel="$(printf '%s\n' "$version_line" | ${pkgs.gnused}/bin/sed -n 's/.*(Linux \([^)]*\)).*/\1/p')"
            built="$(printf '%s\n' "$version_line" | ${pkgs.gnused}/bin/sed -n 's/.*built on \([0-9:+ TZ-]*\).*/\1/p')"
            if [[ -z "$built" ]]; then
              built="$(${pkgs.coreutils}/bin/stat -c '%y' "$entry" | ${pkgs.coreutils}/bin/cut -d. -f1)"
            fi

            title="Sinnix gen $generation"
            [[ -n "$built" ]] && title="$title - $built"
            [[ -n "$kernel" ]] && title="$title - Linux $kernel"
            ${pkgs.gnused}/bin/sed -i "s|^title .*|title $title|" "$entry"
          done

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

    consoleLogLevel = 4;

    kernelParams = [
      "rw"
      "vt.global_cursor_default=0"
      "rd.systemd.show_status=true"
      "rd.udev.log-priority=info"
      "acpi_enforce_resources=lax"
      "vga=current"
      # Low-latency: allow preemption of almost all kernel code paths.
      # ~2-5% throughput cost on heavy compilation, negligible on 24-thread CPU.
      "preempt=full"
      # Prevent USB device autosuspend — eliminates wakeup latency on mouse/keyboard
      "usbcore.autosuspend=-1"
      # Crucial P3 /realm policy: keep the storage controller in active states
      # so Btrfs metadata writeback has predictable command latency.
      "nvme_core.default_ps_max_latency_us=0"
      # Keep PCIe link power management out of the /realm storage path.
      "pcie_aspm=off"
      # Keep boot diagnostics visible without debug-level systemd spam.
      "loglevel=4"
      "systemd.default_timeout_start_sec=30s"
      "systemd.default_timeout_stop_sec=10s"
    ]
    ++ lib.optionals (config.sinnix.gpu.mode == "dual") [
      # xe loads as a transitive dep of nvidia and claims the iGPU PCI ID (0xa780)
      # before i915 can bind. force_probe opts the UHD 770 into xe's binding path.
      "xe.force_probe=a780"
    ];
  };

  systemd.services.sinnix-disable-nvme-aspm = {
    description = "Disable ASPM on the /realm NVMe PCIe link";
    wantedBy = [ "multi-user.target" ];
    before = [ "multi-user.target" ];
    after = [ "local-fs.target" ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
    };
    script = ''
      disable_aspm() {
        dev="$1"
        value="$(${pkgs.pciutils}/bin/setpci -s "$dev" CAP_EXP+0x10.w)"
        masked="$(printf '%04x' "$((0x$value & ~0x3))")"
        ${pkgs.pciutils}/bin/setpci -s "$dev" CAP_EXP+0x10.w="$masked"
      }

      disable_aspm 00:06.0
      disable_aspm 02:00.0
    '';
  };

  hardware.enableRedistributableFirmware = true;
  hardware.cpu.intel.updateMicrocode = true;
}
