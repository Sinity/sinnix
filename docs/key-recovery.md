# Master Key Escrow & Disaster Recovery

This document describes how the agenix master key is escrowed and how to recover
full access to the system's secrets from nothing but an escrow blob + a passphrase.

> **2026-07 change — secrets moved out of the git repo.** `secret/*.age` and
> `secrets.nix` used to live inside this repo (encrypted, but still git
> history payload). They now live at `/realm/data/secrets/sinnix/`, outside
> the checkout entirely (see `modules/secrets.nix`). `git clone` alone no
> longer recovers the encrypted secrets — only the Nix module code that
> knows where to look for them. **This removes GitHub as an off-site backup
> for the encrypted secrets themselves**; the Hetzner Storage Box off-site
> target in `modules/services/borg-target.nix` is scaffolded but not
> currently active, so the only remaining backup for `secret/`+`secrets.nix`
> is the local `/realm` → `/outer-realm` Borg pipeline (see
> `modules/backup.nix`) — both drives in the same machine/location. Given the
> whole directory is small (~30 files, well under 1 MB), the simplest
> mitigation is to fold a copy of `/realm/data/secrets/sinnix/` into the same
> escrow blob described below, so a truly off-site recovery path still
> exists. Not yet done — flagged here as a real, not-hypothetical gap.

## What the keystone is

Every secret in `secrets.nix` is encrypted to the **user key**
`~/.ssh/id_ed25519` (`/persist/home/sinity/.ssh/id_ed25519`). That single
411-byte file decrypts the entire agenix store — API keys, wifi PSK, borg backup
passphrase, root password, user password. It is also wired as an agenix identity
path in `modules/secrets.nix`.

The sinnix repo is **private** on GitHub (`github.com/Sinity/sinnix`); recovering
the Nix module code requires `~/.ssh/id_ed25519_github` (the SSH key that
authenticates `git clone git@github.com:Sinity/sinnix`), but — see the callout
above — that clone no longer carries the encrypted `.age` files themselves.

Both keys are therefore escrowed together. They are small and stable; the repo is
the live source of truth for the (rotating) secrets, so only the keys are escrowed,
not the secret values.

### Which key does what (they are NOT interchangeable)

| Key                 | Role                                                                  | Decrypts secrets? |
| ------------------- | --------------------------------------------------------------------- | ----------------- |
| `id_ed25519`        | agenix `user` recipient — the only escrowed key that runs `agenix -d` | **Yes**           |
| `id_ed25519_github` | SSH auth to clone the private repo; no agenix role                    | No                |

Cold recovery needs both, in sequence: the **github** key fetches the encrypted
material (`git clone` → you now hold the `.age` ciphertexts), then the **user** key
opens it. Neither alone is sufficient — github-key-only is unreadable ciphertext;
user-key-only has nothing to read.

(A third key, the host key `/persist/etc/ssh/ssh_host_ed25519_key`, is also an
agenix recipient and can decrypt, but it is regenerable per-host and deliberately
not escrowed — `id_ed25519` is the durable human keystone that survives any host.)

## The escrow artifact

A single passphrase-wrapped blob, `sinnix-keys.age`, containing a tar of:

- `id_ed25519`, `id_ed25519.pub` — decrypts every agenix secret
- `id_ed25519_github`, `id_ed25519_github.pub` — clones the private repo

It is encrypted with `age -p` (scrypt + passphrase). The **same ciphertext** is
copied to multiple media (pendrive, Google Drive, phone). No medium needs to be
trusted: durability comes from having N copies, safety comes from the passphrase.

### Passphrase custody (the single point of failure)

- Strong and memorable.
- Stored in your memory **plus** a paper copy kept physically separate from the
  drives, optionally a password-manager entry.
- **Never** stored in plaintext alongside any blob (not on the same
  pendrive/Drive/phone). A blob + its passphrase in one place = no protection.

## Creating / refreshing the escrow blob

Run interactively (the passphrase prompt must never pass through an agent or a
shared transcript):

```bash
cd /persist/home/sinity/.ssh
tar -cf /tmp/keybundle.tar \
    id_ed25519 id_ed25519.pub id_ed25519_github id_ed25519_github.pub

# Wrap with a passphrase (prompts twice):
age -p /tmp/keybundle.tar > /tmp/sinnix-keys.age

# Verify it round-trips to the live keys BEFORE trusting/distributing it.
# Empty output + exit 0 means the decrypted archive is byte-identical to disk:
age -d /tmp/sinnix-keys.age | tar --compare -C /persist/home/sinity/.ssh \
    && echo RESTORE_OK

# Remove the plaintext bundle once RESTORE_OK is printed:
shred -u /tmp/keybundle.tar
```

Distribute `/tmp/sinnix-keys.age` **only after `RESTORE_OK`**:

- Pendrive: `/mnt/pendrv/keys/sinnix-keys.age`
- Google Drive: upload `/tmp/sinnix-keys.age` (this wrapped blob — never the raw key)
- Phone: copy from pendrive or Drive

> Flash/btrfs erasure caveat: `shred`/`rm` do **not** guarantee erasure on
> copy-on-write filesystems or flash media (old extents linger; wear-leveling
> remaps blocks). To truly remove plaintext key material from a USB stick, do a
> full-device `blkdiscard`/overwrite or physically destroy it. A file delete only
> removes the casual reference.

## Recovery from total loss

Starting from any machine with `age` (and the escrow blob + passphrase):

```bash
# 1. Recover both keys from the escrow blob.
mkdir -p ~/.ssh && chmod 700 ~/.ssh
age -d /path/to/sinnix-keys.age | tar -x -C ~/.ssh   # prompts for passphrase
chmod 600 ~/.ssh/id_ed25519 ~/.ssh/id_ed25519_github

# 2. Clone the private config repo using the recovered GitHub key.
GIT_SSH_COMMAND='ssh -i ~/.ssh/id_ed25519_github' \
    git clone git@github.com:Sinity/sinnix
cd sinnix

# 3. Restore the encrypted secrets themselves to /realm/data/secrets/sinnix/
#    (secret/*.age + secrets.nix). They are NOT in the git clone above — see
#    the 2026-07 callout at the top of this doc. Recover them either from:
#      a. the local Borg /realm backup (modules/backup.nix), if that drive
#         survived whatever caused the loss, or
#      b. a copy folded into the escrow blob, if that mitigation has since
#         been done (recommended — see the callout above).
mkdir -p /realm/data/secrets/sinnix
# ... restore secret/ and secrets.nix into that directory from (a) or (b) ...

# 4. Decrypt any secret with the recovered user key. Examples:
cd /realm/data/secrets/sinnix
nix run github:ryantm/agenix -- -d secret/borg-passphrase.age   # restore backups
nix run github:ryantm/agenix -- -d secret/root-password.age
```

With `borg-passphrase` recovered you can open the off-site/local Borg repositories
(see `modules/backup.nix`) and restore data; with the user/root passwords you can
re-provision the host.

## Invariants

- The key, the blob, and the passphrase are **never** committed to this repo.
- The blob is the only thing that may live on untrusted media, and only because it
  is passphrase-wrapped.
- Re-run the create/verify steps after any key rotation, and re-distribute.
