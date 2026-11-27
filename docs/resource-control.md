# Resource control

Agent work on sinnix-prime can slow itself down or lose its own jobs; it
cannot take the desktop, the live services or the host with it. Memory is
held to that by a budget that sums to physical memory, the disk by IOCost
weights. Pool widths only make builds efficient inside the budget, and
agentctl starts a job only when the job plane's free memory covers its
reservation ([agentctl pools](agentctl.md#pools)).

## Memory budget

Every consumer outside agent work has a line: memory the kernel keeps for it
(`MemoryMin`, or `MemoryLow` sized to its measured working set). Agent work
gets what the lines leave. The numbers live in `hostMemory` and `agentMemory`
in `flake/data/runtime-defaults.nix`; evaluation fails if the job plane's or
the tool slice's ceiling exceeds that remainder.

| Line                                | GiB  | Mechanism                                                                  |
| ----------------------------------- | ---- | -------------------------------------------------------------------------- |
| Physical memory (`MemTotal`)        | 31.2 |                                                                            |
| Kernel memory and free-page reserve | 2.0  | uncharged slab, vmalloc and stacks (~1.3), `min_free_kbytes` and watermarks |
| zram store                          | 4.75 | zram device size (16 GiB) at the measured 3.3:1 compression                |
| Desktop: apps, session, shell       | 6.5  | `MemoryMin` on app (4), session (1.5) and desktop-shell (1)               |
| PostgreSQL                          | 5.5  | `MemoryLow`; 4.3 of it are the huge pages of shared buffers              |
| sinexd                              | 1.0  | `MemoryLow`                                                                |
| NATS, journald capture              | 0.25 | `MemoryLow` 128M each                                                     |
| Polylogue daemon                    | 1.5  | `MemoryLow`                                                                |
| Session producer                    | 0.25 | `MemoryLow`                                                                |
| Other system services               | 1.0  | `MemoryLow` on `system.slice`                                             |
| Recovery services                   | 0.25 | `MemoryLow` on `system-critical.slice`                                    |
| User capture producers              | 0.5  | `MemoryLow` on the user `background.slice`                                |
| **Left for agent work**             | 7.65 |                                                                            |

Inside agent work: interactive CLIs (`agent-cli.slice`) keep 3 GiB protected
and have no ceiling; tool commands and MCP servers (`agent-tool.slice`)
stop at 5; the job plane (`agent-ctl.slice`) stops at 7.5, room for the largest
single job (a Sinex focused build peaks at 6.9 GiB). A pool slice sets its own limit only where it is tighter than
the plane's. Jobs whose reservations together exceed the plane wait in the
queue instead of starting ([memory admission](agentctl.md#memory-admission)).

An agent's tool commands and MCP servers share one unit,
`agent-tool-<agent unit>.service`, which `agent-tool-command` starts with the
agent's first command and which stops when the agent's own unit does. Each
command runs in its own leaf cgroup of that unit (`cmd-<pid>`) with the memory
controller enabled, so the kernel and systemd-oomd still act on one command;
the unit's own process removes the leaves of finished commands. A unit per
command would be a journal line per command, with no end recorded for a scope.
A helper launch of an agent CLI that is not a session (a version or help
query, Codex's `app-server proxy`) stays where it was started and gets no
unit.

Each live service also has a ceiling that ends a leak inside its own unit:

| Unit                  | `MemoryHigh` | `MemoryMax` | `MemorySwapMax` | Two-week peak             |
| --------------------- | ------------ | ----------- | --------------- | ------------------------- |
| PostgreSQL            | 8G           | 9G          | -               | 8.1G (at its high)        |
| sinexd                | -            | 8G          | 2G              | 6.0G resident, 2G swapped |
| NATS                  | 1G           | 1.5G        | -               | 0.7G                      |
| journald capture      | 1G           | 2G          | -               | 2G, page cache            |
| Polylogue daemon      | -            | 8G          | 1G              | 5.3G resident             |
| User capture producers| -            | 3G          | -               | 0.3G                      |

The Polylogue daemon, its index build included, must fit 8 GiB resident and
1 GiB swapped; beyond that the kernel kills it inside its own unit.

PostgreSQL's huge pages (2,202 pages of 2 MiB, 4.3 GiB, reserved at boot for
4 GiB of shared buffers) are one line with the rest of its memory: the cgroup
filesystem is mounted with `memory_hugetlb_accounting`, so the pages count in
`postgresql.service`'s `memory.current` and its 8G high and 9G max include
them, leaving about 3.7 GiB for backends and page cache. The reservation is
RAM whether PostgreSQL uses it or not, so it is sized by how hot the pool is:
on 2026-11-16 `pg_buffercache` (installed in the `postgres` database) showed
67% of buffers at usage count 3-5 and 14% at 0-1, for a 196 GB database whose
reads land on the QLC drive. The pool stays at 4 GiB. Shrinking it is worth
revisiting if, at steady state, more than about 40% of buffers sit at usage
count 0-1 while the cluster's block reads (`pg_stat_database.blks_read`) and
the unit's `workingset_refault_file` stay low.

The cgroup filesystem is mounted with `memory_recursiveprot`: protection a
consumer does not use passes to its siblings. The user slice's `MemoryLow`
therefore equals the sum of the lines below it (desktop, user live services,
capture producers), so agent work, the other child of the user manager,
inherits only the part of those lines currently unused.

Memory a line does not cover is paid for out of agent work's share: the
desktop above its guarantee, a service between its line and its ceiling, Nix
builds (`nix-build.slice`, 10G high, 12G max) and backups. The kernel reclaims
unprotected memory first, and agent work is the only large unprotected
consumer.

### What is killed

At a ceiling (the job plane, the tool slice) the kernel first
reclaims and swaps inside it, which slows the work down, and then kills
inside it at once. No agent slice has a `MemoryHigh`: a `MemoryHigh` below a
ceiling throttles without ever killing. On the job and tool slices it held
runaway allocators throttled for minutes; on the CLI slice, with its swap full,
it held every session asleep while the kernel evicted and re-read the CLIs'
own code, until the host was rebooted. oomd's pressure rule is not used here
either: it killed bystanders that were being reclaimed. The victim is chosen by OOM score, and the scores rank the kinds
of agent work:

1. agentctl job units, `OOMScoreAdjust=900` (measurement jobs 100). A job unit
   carries `OOMPolicy=kill`, so the whole job ends, and agentctl reports it as
   `out-of-memory` with `killed: out of memory` in its
   log. Borg drains rank with them at 900 and resume on their next run.
2. Rebuilds (their `nix-build.slice` unit) and the Nix daemon's builders, 850.
3. Tool commands, 800 (`agent-tool-command`).
4. The agent CLIs themselves, 300.

The kernel adds to each rank the process's share of RAM (about 78 points for
2.5 GiB), and kills the highest total. Rebuilds sit below agentctl jobs because
activation is how the host's own fixes land: at an equal rank a rebuild's
2.5 GiB evaluation was the largest process and died to agent compiles four
times in a row (2026-11-24). They sit above tool commands so that a host OOM
during a large build does not kill tiny tool commands first, freeing nothing.

Compare (`sinnix rank desktop`) runs in its own scope in `app.slice`, so its
memory counts on the apps line whatever launched it, with `MemoryHigh=3G`
and `MemoryMax=4G`. Compare decodes with `nvdec`, which keeps frames on the
GPU; each playing 8K video still costs about 640 MiB resident for its CUDA
context and decoder (half NVIDIA driver mappings, half heap), so two
playing measure 1.7 GiB and frames alone 0.4 GiB. Closing a player returns
that memory; its launcher sets `MALLOC_ARENA_MAX=2` so glibc does not keep
an arena per finished decoder thread.

systemd-oomd ends sustained thrash before the kernel has to: it kills the job
with the most reclaim when the job plane's memory pressure stays above 40% for
15 s (pytest and bulk pools: 50% for 30 s), the tool command with the most
reclaim when `agent-tool.slice` stays above 50% for 20 s, and the job or tool
command using the most swap when memory and swap are both more than 90%
used (about 3.3 GiB still available). pueued, whose children
are every running job's wrapper, is omitted from oomd's choices
(`ManagedOOMPreference=omit`). No oomd policy covers a slice that holds an
agent CLI, the desktop or a service.

The same scores apply if the host as a whole runs out (a service or the
desktop far above its line): job units and tool commands rank above Chrome's
renderers (200-300) and everything else. earlyoom remains the last resort
when available memory and swap are both nearly gone and memory pressure is
high.

### Swap

zram is the only swap. Its store is part of the budget: the 16 GiB device holds
about 4.75 GiB of RAM at the measured 3.3:1 ratio. Swapping to it is far
cheaper than re-reading files, so `vm.swappiness` is 170: the kernel compresses
cold anonymous memory before it drops page cache. The device size is the only
bound. A resident limit below it would make swap writes fail while swap still
reads as free, so the kernel would keep reclaiming and no swap-based kill rule
would fire. Pages that compress worse than 3.3:1 grow the store past its line,
and that is paid for like any other overrun. The tool slice and the job plane
may each swap 2 GiB, sinexd 2 GiB, the Polylogue daemon 1 GiB; interactive
sessions are not limited, so idle ones compress into zram.

## Disk

The workstation's IOCost initializer enables IOCost on every physical block
device (`sinnix-iocost-init`), so `IOWeight` is a share of the device under
contention; an idle share is lent to whoever is busy. A device with a measured
cost model and latency targets (`sinnix.machine.blockCost`) has its virtual
rate lowered when the targets are missed, which is what makes the weights take
effect before the device saturates.

| Device                      | Holds                                     | IOCost                                                    |
| --------------------------- | ----------------------------------------- | --------------------------------------------------------- |
| NVMe (Crucial P3, QLC)      | `/realm`: worktrees, builds, PostgreSQL   | measured model, p90 read 10 ms, p90 write 50 ms, rate 50-600% |
| SATA SSD (Crucial MX500)    | `/`, `/nix/store`, `/home`                | kernel automatic model, no latency targets               |

Weights at the root: system `live.slice` 400, `user.slice` 400, `system.slice`
100, `nix.slice` 25, `background.slice` 20. Inside the user manager the
desktop and live slices carry 300 and `agent.slice` 25; inside agent work the
CLIs 100, tools 90 and the job plane 100, whose pools range from 300 (agent
workers) down to 5 (copies and offloads).

IOLatency targets must not overlap IOCost on any device: the two controllers
use incompatible modes of the same block-cgroup delay state (`blkcg_set_delay`
against `blkcg_use_delay`), which the kernel's helper contract prohibits. The
rendered controller-exclusion check covers declared slices and services.

The QLC NVMe sustains about 25-50 MB/s of writes once its SLC cache is spent.
No weight makes it faster: a write-heavy agent job beside PostgreSQL shares
that rate, and the latency targets keep PostgreSQL's reads ahead of it.

Primary contract: [Linux block-cgroup delay helpers](https://raw.githubusercontent.com/gregkh/linux/v6.18.50/block/blk-cgroup.h#L373-L425).

### Full-volume backup admission and live archive activation

The Realm, Persist and genome drains share the existing borgdrain.slice
(6 GiB resident in total, no swap). Before starting, each waits for at least
8 GiB available RAM and a current Polylogue index, or a confirmed inactive
user manager. An unavailable active index status is not readiness. Waiting
takes no Borg lock. Local snapshot acquisition and the hourly custody jobs
remain independent.

The systemd admission timer checks only running full-volume drains. If a
live rebuild starts after admission, or memory crosses the emergency
watermark, it requeues the affected drain through the same admission wait;
the unacknowledged snapshot and any Borg checkpoint remain recoverable.
The upper start watermark and lower emergency watermark avoid oscillation.
This is a sampled guard, not a host-wide atomic memory reservation.

Home Manager uses sd-switch's keep-old policy for Polylogue: switching
the workstation installs the unit configuration but never restarts its
existing process. For an intentional product or archive upgrade, verify
the live status, prepare the new archive and explicitly restart
polylogue-live.service only at the chosen cutover. Do not treat successful
activation alone as evidence of a running daemon upgrade. The service keeps
normal automatic recovery after an unexpected exit.
