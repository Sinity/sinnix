# Bootstrapping `sinnix-ethereal`

`sinnix-ethereal` is the headless NixOS member of the Sinnix fleet. Its first
installation uses nixos-anywhere and Disko; subsequent deployments use the
same flake through the Colmena wrapper.

The host definition lives under `hosts/sinnix-ethereal/` and composes the
cloud profile, declarative storage, Tailscale connectivity, and the replica
Sinex role.

## Prerequisites

- A provisioned x86-64 server booted into a Linux rescue environment with root
  SSH access.
- Disk identifiers matching `hosts/sinnix-ethereal/disko.nix`, reviewed before
  running the destructive first install.
- The private secret overlay populated for this host and encrypted to an Age
  identity available during activation.
- A pre-authorized Tailscale key in that overlay if the node should join the
  tailnet without interactive login.

Secret payloads are intentionally outside this checkout. The tracked modules
define only their runtime contracts and expected paths.

## Initial installation

From a checkout of Sinnix:

```bash
nix run .#deploy-ethereal -- root@<rescue-address>
```

The wrapper invokes nixos-anywhere for `.#sinnix-ethereal`. Disko applies the
declared disk layout, the system closure is installed, and the machine reboots
into NixOS.

This operation destroys data on the disks named by the Disko configuration.
Review the resolved target and the host's storage module before running it.

After reboot:

```bash
ssh root@<rescue-address> hostname
```

Once Tailscale is active, use the tailnet name/address instead of the rescue
address.

## Steady-state deployment

```bash
nix run .#apply-all -- --on sinnix-ethereal
```

Running `apply-all` without a host selector targets the configured fleet. Use
the selector for ordinary single-host work so an unrelated workstation change
is not applied accidentally.

## Failure recovery

- **Install interrupted before reboot:** return to the rescue environment and
  rerun `deploy-ethereal`; Disko recreates the declared layout.
- **Closure transfer interrupted:** rerun the same command. Existing Nix store
  paths are reused where possible.
- **First boot unavailable over the network:** inspect the serial/KVM console;
  the cloud profile enables a serial console and emergency boot diagnostics.
- **Tailscale did not join:** inspect `tailscaled-autoconnect.service`, verify
  that the key is present and still valid, then rerun the activation after
  correcting the private overlay.

## Relevant source

| Path | Role |
| --- | --- |
| `hosts/sinnix-ethereal/` | Host composition, hardware, storage, boot, and networking. |
| `modules/profiles/cloud.nix` | Headless defaults and remote-operability posture. |
| `modules/services/tailscale.nix` | Tailnet service and enrollment contract. |
| `modules/services/sinex/bridge.nix` | Translation from Sinnix role options to the upstream Sinex module. |
| `flake/deploy.nix` | `deploy-ethereal` and `apply-all` command implementations. |
