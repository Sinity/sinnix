# Interactive disk isolation

Chrome uses its persistent `~/.config/chrome-ws` profile and two private tmpfs mounts declared by `modules/features/desktop/browser.nix`:

| Purpose         | Path                       | File-data limit | Inode limit | Behavior                                                                                                |
| --------------- | -------------------------- | --------------- | ----------- | ------------------------------------------------------------------------------------------------------- |
| HTTP cache      | `/run/sinnix-chrome-cache` | 256 MiB         | 8192        | Chrome targets 128 MiB; the filesystem bounds aggregate use across profiles                             |
| Temporary files | `/run/sinnix-chrome-tmp`   | 512 MiB         | 4096        | The package wrapper sets `TMPDIR`, including direct `google-chrome` and `google-chrome-stable` launches |

Both mounts allocate on demand, use `noswap`, and are accessible only to the configured desktop user. Maximum added file-data RAM is 768 MiB (2.4% of 32 GiB), plus kernel metadata bounded by the inode counts. Unused capacity consumes no file-data RAM. `noswap` prevents these files competing for the zram swap tier. See the [kernel tmpfs contract](https://docs.kernel.org/filesystems/tmpfs.html).

The temporary-files override removes Chrome's dependency on the user manager's agent-oriented `/realm/tmp/work`. The cache change removes HTTP cache IO on the root SSD; its performance benefit depends on workload. Cache contents can be fetched again after reboot. Temporary allocations can fail at 512 MiB; monitor usage during large browser workloads. Downloads, profile databases, cookies, extension storage, shader caches and capture destinations retain their existing locations. Activation copies or deletes no existing browser files. Existing Chrome processes keep their original paths until a full normal browser exit and relaunch.

On sinnix-prime, `sinnix-realm-writeback.service` applies `max_ratio=25` and `strict_limit=1` to the BDI reached through `/sys/fs/btrfs/<realm-filesystem-uuid>/bdi`, after `realm.mount` and `systemd-sysctl.service`. Btrfs has its own backing device information (BDI); setting the raw NVMe BDI does not apply that policy to Btrfs writes. The filesystem UUID comes from the host's storage declaration, so kernel `btrfs-N` numbering is irrelevant.

The existing global dirty limit remains 1 GiB and the background threshold remains 128 MiB. Realm receives a 25% writeback share, nominally 256 MiB. This allocates no extra RAM and limits dirty backlog rather than total Btrfs metadata or clean cache. Kernel accounting and in-flight writes can exceed a nominal dirty threshold. Synchronous IO and shared Btrfs log, transaction and extent locks can still stall. See the [kernel BDI controls](https://docs.kernel.org/admin-guide/abi-testing.html).

## Verification

Source checks, without activation:

```sh
nix build --no-link -L .#checks.x86_64-linux.browser-ram-cache
nix build --no-link -L .#checks.x86_64-linux.realm-writeback
```

The browser fixture exercises the evaluated package override through both direct aliases and `sinnix-chrome`, including argument preservation and an inherited slow-disk `TMPDIR`. It checks the evaluated mount limits. The writeback fixture executes the host's script against a synthetic Btrfs UUID-to-BDI symlink, with a different BDI number, and verifies that other BDIs remain untouched and missing filesystems fail. It also forces the rendered systemd unit and mount/sysctl ordering.

After a separately authorized activation, compare the installed revision with the integrated commit and inspect the new policy:

```sh
nixos-version --configuration-revision
systemctl show sinnix-realm-writeback.service -p ActiveState -p SubState -p Result
findmnt --mountpoint /run/sinnix-chrome-cache -o TARGET,SOURCE,FSTYPE,SIZE,OPTIONS
findmnt --mountpoint /run/sinnix-chrome-tmp -o TARGET,SOURCE,FSTYPE,SIZE,OPTIONS
stat -c '%a %u %n' /run/sinnix-chrome-cache /run/sinnix-chrome-tmp
cat /sys/fs/btrfs/43701cf7-7880-4e0c-9725-b6e12d91898a/bdi/max_ratio
cat /sys/fs/btrfs/43701cf7-7880-4e0c-9725-b6e12d91898a/bdi/strict_limit
cat /sys/fs/btrfs/43701cf7-7880-4e0c-9725-b6e12d91898a/bdi/max_bytes
```

Expect `active/exited`, `Result=success`, tmpfs sizes 256 MiB and 512 MiB with `noswap`, mode 700 owned by the desktop UID, and BDI values `25`, `1`, `268435456`. The old raw-device value may persist until reboot; the filesystem BDI is the deciding read.

After a full normal Chrome exit and relaunch through the installed package, use `chrome://version` to check `--disk-cache-dir=/run/sinnix-chrome-cache`, `--disk-cache-size=134217728`, and the original profile path. During normal browsing and the same sort of agent disk load, check open Chrome files and capacity:

```sh
df -B1 /run/sinnix-chrome-cache /run/sinnix-chrome-tmp
sudo python3 - <<'PY'
from pathlib import Path
import collections
import os
paths = collections.Counter()
for proc in Path('/proc').glob('[0-9]*'):
    try:
        if (proc / 'comm').read_text().strip() != 'chrome':
            continue
        for fd in (proc / 'fd').glob('*'):
            try:
                target = os.readlink(fd)
            except OSError:
                continue
            for root in ('/run/sinnix-chrome-cache/', '/run/sinnix-chrome-tmp/', '/realm/tmp/work/'):
                if target.startswith(root):
                    paths[root] += 1
    except OSError:
        continue
print(dict(paths))
assert not paths['/realm/tmp/work/'], 'Chrome still has files open on Realm scratch'
PY
```

Repeat 50 ms D-state thread sampling with stacks and current syscall paths under high host IO PSI. Rank concurrent thread observations separately from elapsed wall time and from per-cgroup PSI. Attribute fsync/read/write descriptors at the time of the sample; a process-wide descriptor list captured earlier can become stale. For `openat`/`unlink`, inspect the pathname argument rather than inferring its filesystem from the profile path. Expected result: Chrome temporary-file operations no longer enter Btrfs on Realm. Low-pressure idle use and the static fixtures do not establish that result or prove operator-visible responsiveness under load.
