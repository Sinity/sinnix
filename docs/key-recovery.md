# Key escrow and disaster recovery

How to recover access to the system's secrets from an escrow blob and its
passphrase.

## What has to survive

- **`~/.ssh/id_ed25519`** (`/persist/home/sinity/.ssh/id_ed25519`). Every
  agenix secret is encrypted to this key, so this one small file decrypts all
  of them: API keys, the Wi-Fi PSK, the Borg passphrase, the root and user
  passwords. `modules/secrets.nix` uses it as an agenix identity.
- **The encrypted secrets** (`secret/*.age` and `secrets.nix`). They live in
  `/realm/state/secrets/sinnix/`, outside this repository. Their only backups
  are the local Borg repositories on `/outer-realm`, in the same machine.
  Include this directory in the escrow blob and redistribute it to give the
  ciphertexts an off-site copy. Existing blobs need refreshing.

The repository itself is public (`github.com/Sinity/sinnix`), so it can be
cloned over HTTPS without any key. The host key
`/persist/etc/ssh/ssh_host_ed25519_key` is also an agenix recipient, but it is
per-host and regenerable, so it is not escrowed.

## The escrow blob

`sinnix-keys.age` is a tar of the SSH keys in `~/.ssh` (`id_ed25519` and the
GitHub push key `id_ed25519_github`, with their `.pub` files) and
`/realm/state/secrets/sinnix/`, encrypted with `age -p`. The same ciphertext
goes on several media (pendrive, phone). The
Google Drive copies were deleted in July 2026; check before relying on one.
Safety comes from the passphrase, so no medium needs to be trusted.

Keep the passphrase in memory and on paper stored apart from the media. Never
store it next to a blob.

## Creating or refreshing the blob

Run this yourself; the passphrase prompt must not pass through an agent.

```bash
set -o pipefail
tar -cf /tmp/keybundle.tar -C /persist/home/sinity/.ssh \
    id_ed25519 id_ed25519.pub id_ed25519_github id_ed25519_github.pub \
    -C / realm/state/secrets/sinnix
age -p /tmp/keybundle.tar > /tmp/sinnix-keys.age

# Check the blob round-trips before distributing it:
age -d /tmp/sinnix-keys.age | tar --compare \
    -C /persist/home/sinity/.ssh \
    id_ed25519 id_ed25519.pub id_ed25519_github id_ed25519_github.pub \
    -C / realm/state/secrets/sinnix \
    && echo RESTORE_OK
shred -u /tmp/keybundle.tar
```

Copy `/tmp/sinnix-keys.age` to the media only after `RESTORE_OK`. `shred` does
not reliably erase data on flash or copy-on-write filesystems; to remove
plaintext keys from a USB stick, overwrite the whole device or destroy it.

## Recovery

```bash
# 1. Recover the keys and encrypted secrets from a refreshed blob.
mkdir -p ~/.ssh && chmod 700 ~/.ssh
set -o pipefail
age -d /path/to/sinnix-keys.age | tar -x \
    -C ~/.ssh id_ed25519 id_ed25519.pub id_ed25519_github id_ed25519_github.pub \
    -C / realm/state/secrets/sinnix   # asks for the passphrase
chmod 600 ~/.ssh/id_ed25519 ~/.ssh/id_ed25519_github

# 2. Get the configuration.
git clone https://github.com/Sinity/sinnix.git

# 3. Older blobs contain only keys. For those, restore the encrypted secrets
#    into /realm/state/secrets/sinnix/ from the /outer-realm Borg repositories
#    (modules/backup.nix), if that drive survived.

# 4. Decrypt with the recovered key, for example:
cd /realm/state/secrets/sinnix
nix run github:ryantm/agenix -- -d secret/borg-passphrase.age
nix run github:ryantm/agenix -- -d secret/root-password.age
```

The Borg passphrase opens the backup repositories; the passwords let you
re-provision the host.

## Rules

- Keys, blob and passphrase are never committed.
- Only the passphrase-wrapped blob may live on untrusted media.
- Refresh and redistribute the blob after any key rotation or encrypted-secret change.
