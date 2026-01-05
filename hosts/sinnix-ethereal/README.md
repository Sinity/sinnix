# sinnix-ethereal bringup notes

These are the most common blockers when trying to boot/deploy this host.

Known blockers
- Private flake input: `sinex` is fetched via `git+ssh://git@github.com/Sinity/sinex`. Without a GitHub SSH key on the target, flake evaluation fails early.
- Agenix secrets: secrets decrypt only if the host SSH key or `/home/sinity/.ssh/id_ed25519` is present. New VPS host keys require re-encrypting `secrets.nix` or copying the user key.
- Boot/device assumptions: config expects BIOS + GRUB and `/dev/vda`. UEFI-only VPSes or NVMe disks (`/dev/nvme0n1`) need `boot.nix` / `disko.nix` tweaks.
- Resource tightness: 1 GiB RAM + 16 GiB disk is fragile. 4 GiB swap and large journald retention can fill disk; Nix builds can OOM without binary caches or a remote builder.

If a bringup fails, check these first before digging into module logic.
