# sinnix-ethereal bootstrap

End-to-end procedure from "AX42 freshly provisioned with default Hetzner
image" to "ethereal joined the tailnet, ready for service deploys".

## Prereqs

- Hetzner AX42 ordered and in `provisioned` state in the robot console.
- The default Hetzner rescue/installer image is bootable (no custom image
  required — nixos-anywhere installs from any Linux that has SSH).
- A Tailscale auth key generated in the admin console with `tag:infra`
  preauthorized for that node. (`https://login.tailscale.com/admin/settings/keys`)
- Three agenix secrets created locally on the workstation:

  ```bash
  agenix -e secret/tailscale-authkey.age   # paste the tskey-auth-...
  agenix -e secret/sinex-remote-db.age     # KEY=value lines for sinex
  agenix -e secret/borg-storagebox-ssh.age # private key for the StorageBox
  ```

  These are declared in `secrets.nix` but the .age files don't exist
  until the operator creates them; modules that would consume them stay
  inert until then.

- The workstation's `ssh-agent` has a key authorized for the AX42 rescue
  image's `root@` account (Hetzner gives you a one-time root password via
  the robot console after provisioning).

## Step 1 — initial install via nixos-anywhere

Estimated wall-clock: 15–25 minutes. Most of it is closure transfer.

```bash
cd /realm/project/sinnix
nix run .#deploy-ethereal -- root@<ax42-ip>
```

The wrapper invokes:

```bash
nixos-anywhere --flake .#sinnix-ethereal --target-host root@<ax42-ip>
```

What happens:

1. nixos-anywhere SSHes in, builds a tiny kexec installer locally, copies
   it over, kexecs into it.
2. disko (per `hosts/sinnix-ethereal/disko.nix`) wipes the disks and
   formats the dual-NVMe layout: nvme0n1 → ESP + ext4 root; nvme1n1 →
   ext4 `/var/lib/data`.
3. The system closure is copied from your workstation; nixos installs;
   systemd-boot is installed on the ESP.
4. The box reboots into the real NixOS system.

Verify SSH still works after reboot:

```bash
ssh root@<ax42-ip> uname -a
```

## Step 2 — Tailscale join

The cloud profile + tailscale module brings tailscaled up on first boot,
and the agenix-decrypted authkey performs the join. Confirm from the
workstation:

```bash
tailscale status | grep ethereal
ssh root@sinnix-ethereal hostname     # via MagicDNS once it's up
```

If tailscale didn't auto-join (key already revoked, ACL mismatch),
inspect `journalctl -u tailscaled-autoconnect -e` on the box. To re-key
without a full rebuild:

```bash
ssh root@<ax42-ip> tailscale up --auth-key=tskey-auth-... --advertise-tags=tag:infra
```

## Step 3 — steady-state apply

From this point forward, deploys use colmena:

```bash
nix run .#apply-all -- --on sinnix-ethereal
```

`apply-all` with no args targets `@all` (both prime and ethereal).

## Recovery — midway failure

- **disko wipe interrupted**: rerun `deploy-ethereal`. The wipe is
  idempotent — disko unmounts and re-formats.
- **closure transfer dies**: rerun `deploy-ethereal`. nixos-anywhere
  resumes via the SSH-backed nix store path.
- **first boot wedges**: Hetzner robot KVM console provides serial access
  on ttyS0 (the cloud profile pre-wires `console=ttyS0,115200n8`). Use
  the boot.shell_on_fail emergency shell to inspect.

## Where to look in the repo

- `hosts/sinnix-ethereal/` — host-specific configs
- `modules/profiles/cloud.nix` — headless posture
- `modules/services/tailscale.nix` — tailnet join
- `modules/services/sinex.nix` + `modules/services/sinex/bridge.nix` —
  `deploymentRole = "replica"` branch
- `flake/deploy.nix` — `deploy-ethereal` / `apply-all` wrappers
- `tailscale-acl.json.template` — ACL shape (copy-paste into admin console)

## Locked decisions referenced by this scaffold

- **Binary cache: Attic, self-hosted on ethereal.** Per Build Plan §E6, the
  ethereal host will run `services.atticd` to serve a private Nix substituter
  at `attic.sinity.dev`, instead of paying for Cachix. The atticd service is
  NOT enabled by this scaffolding — it lands in a follow-up once the bootstrap
  is verified.
- **AirVPN scope: transmission-only via policy routing.** The existing
  `modules/services/airvpn-seed.nix` already wires the WireGuard tunnel with
  a dedicated routing table (`200`) so only Transmission's traffic egresses
  through AirVPN; every other process on the host (including tailscaled,
  sinexd, atticd, ssh, system updates) keeps the normal upstream route.
  Per Build Plan §E14, enabling this on ethereal is conditional on torrent
  frequency — the module is inert until a host imports `sinnix.services.airvpn-seed.enable = true`.
