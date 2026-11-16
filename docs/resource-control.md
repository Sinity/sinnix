# Resource control

Agent work on sinnix-prime can slow itself down or lose its own jobs; it
cannot take the desktop, the live services or the host with it. Memory is
held to that by a budget that sums to physical memory, the disk by IOCost
weights. Pool widths only make builds efficient inside the budget
([agentctl pools](agentctl.md#pools)).

## Memory budget

Every consumer outside agent work has a line: memory the kernel keeps for it
(`MemoryMin`, or `MemoryLow` sized to its measured working set). Agent work's
hard ceiling is what the lines leave. The numbers live in `hostMemory` and
`agentMemory` in `flake/data/runtime-defaults.nix`; evaluation fails if the
agent ceiling exceeds the remainder.

| Line                                | GiB  | Mechanism                                                                  |
| ----------------------------------- | ---- | -------------------------------------------------------------------------- |
| Physical memory (`MemTotal`)        | 31.2 |                                                                            |
| Kernel memory and free-page reserve | 2.0  | uncharged slab, vmalloc and stacks (~1.3), `min_free_kbytes` and watermarks |
| zram store                          | 3.0  | zram `mem_limit` (`zram-resident-limit`)                                  |
| Desktop: apps, session, shell       | 6.5  | `MemoryMin` on app (4), session (1.5) and desktop-shell (1)               |
| PostgreSQL                          | 5.5  | `MemoryLow`; 4.3 of it are the huge pages of shared buffers              |
| sinexd                              | 1.0  | `MemoryLow`                                                                |
| NATS, journald capture              | 0.25 | `MemoryLow` 128M each                                                     |
| Polylogue daemon                    | 1.5  | `MemoryLow`                                                                |
| Session producer                    | 0.25 | `MemoryLow`                                                                |
| Other system services               | 1.0  | `MemoryLow` on `system.slice`                                             |
| Recovery services                   | 0.25 | `MemoryLow` on `system-critical.slice`                                    |
| User capture producers              | 0.5  | `MemoryLow` on the user `background.slice`                                |
| **Left for agent work**             | 9.4  |                                                                            |
| Agent work ceiling                  | 9.0  | `MemoryMax` on `agent.slice`                                              |

Inside agent work: interactive CLIs (`agent-cli.slice`) keep 3 GiB protected,
throttle at 6 and stop at 7; tool commands and MCP servers (`agent-tool.slice`)
stop at 5; the job plane (`agent-ctl.slice`) stops at 8, room for the largest
single job (a Sinnix check peaks at 6.4 GiB). A pool slice sets its own limit only where it is tighter than
the plane's.

Each live service also has a ceiling that ends a leak inside its own unit:

| Unit                  | `MemoryHigh` | `MemoryMax` | `MemorySwapMax` | Two-week peak             |
| --------------------- | ------------ | ----------- | --------------- | ------------------------- |
| PostgreSQL            | 8G           | 9G          | -               | 8.1G (at its high)        |
| sinexd                | -            | 8G          | 2G              | 6.0G resident, 2G swapped |
| NATS                  | 1G           | 1.5G        | -               | 0.7G                      |
| journald capture      | 1G           | 2G          | -               | 2G, page cache            |
| Polylogue daemon      | 3.5G         | 4G          | 1G              | 5.3G resident             |
| User capture producers| -            | 3G          | -               | 0.3G                      |

The Polylogue daemon, its index build included, must fit 4 GiB resident and
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

At a ceiling (`agent.slice`, the job plane, the tool slice) the kernel first
reclaims and swaps inside it, which slows the work down, and then kills
inside it at once. Only the CLIs have a `MemoryHigh` (6), so a session is
throttled rather than killed. A `MemoryHigh` on the other slices held runaway
allocators throttled for minutes without reaching the ceiling, while oomd's
pressure rule killed bystanders that were being reclaimed. The victim is chosen by OOM score, and the scores rank the kinds
of agent work:

1. agentctl job units, `OOMScoreAdjust=900` (measurement jobs 100). A job unit
   carries `OOMPolicy=kill`, so the whole job ends, and agentctl reports it as
   `out-of-memory` with `killed: out of memory in the agent budget` in its
   log.
2. Tool commands, 800 (`claude-tool-scope`).
3. The agent CLIs themselves, 300.

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

zram is the only swap. Its store is part of the budget: the resident limit
holds it to 3 GiB of RAM whatever the pages compress to, and the 9 GiB device
fills at the measured 3:1 ratio together with that limit. A page that would push the store past its limit
is not swapped and stays in its cgroup. Agent work may swap 4 GiB (about 1.3
GiB of the store), sinexd 2 GiB, the Polylogue daemon 1 GiB.

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
