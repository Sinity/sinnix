# Earlyoom VM verification

`earlyoom_vm_verify` retains the synthetic sensor matrix and actual signal
proof. `earlyoom_pressure_vm_verify` exercises actual guest memory, swap and
I/O pressure using the production earlyoom package and rendered arguments.
Neither operation qualifies a live desktop responsiveness window.

Run the real-pressure operation with a fresh absolute output directory on
`/realm`:

```sh
agentctl job start sinnix earlyoom_pressure_vm_verify --workspace /realm/worktree/<checkout> -- /realm/project/sinnix/analysis/<fresh-output>
```

Only `packages.earlyoom-real-pressure-driver` is exported. Broad heavy
checks cannot implicitly execute this pressure VM through the Nix daemon.
The operation reserves 4608 MiB. It builds only the test driver through the
Nix daemon with one builder and two cores, then runs the driver and QEMU as
job descendants under a 4 GiB memory limit, no host swap, and 8 MB/s host
read/write limits on both `/realm` and `/nix` devices. The runtime checks its effective limits and
records QEMU cgroup membership and PIDFD termination. Each run has a fresh
working directory in the exclusive output directory and a private short
runtime/shared/temporary root under `/realm/tmp/work`. Encoded Unix socket
paths are checked before driver launch. The receipt binds that root to the
job; owned QEMU/VDE children terminate before its cleanup. Prior exchange
artifacts are never reused. The VM has 1536 MiB RAM,
two vCPUs, serial-only/no-VGA hardware (checked in the actual guest before
GO), 128 MiB zram and two disks bounded to 512 MiB each. Guest workload
I/O writes at most 256 MiB and reads it once using direct I/O; recovery
may stop that finite operation early. The guest
allocation ramp is capped at 1536 MiB of random anonymous pages and 90 seconds;
compressibility is measured through zram `mm_stat`, rather than assumed from
logical swap use. The test driver has a 360-second test timeout and the host
runner enforces a 420-second runtime deadline. These outer budgets cover cold
setup and export; the allocation/pressure window remains 90 seconds and the
observed gate-to-exit goal remains below 30 seconds.

An independent root sampler records real `/proc` sensors, PID-derived
root/tool/interactive cgroup counters and zram statistics every 20 ms.
The production daemon reaches its first actual poll report before helper
startup, with a bounded 60-second cold-start allowance before pressure.
All fixture helpers load their imports and resident setup before publishing
PID/start-token readiness. Victim allocation and bulk I/O wait for one atomic
GO marker after all helpers are ready and live. The protected observer records
only scheduling timestamps every 50 ms.
Its final gap to the end of the pressure window is included, so a missing
tail cannot appear responsive. The
test requires a captured production kill-gate sample or an explicit contiguous
same-daemon numeric PSI/RAM/swap decision block, real swap use, nonzero
I/O-full pressure, earlyoom SIGKILL of the recorded victim, protected survival,
less than 30 seconds from observed gate to observed victim exit (labeled
independent sampler or daemon observation), and a maximum
protected scheduling gap below five seconds (a headless fixture goal). Guest kernel OOM invalidates the
result. Logs and raw measurements remain in the requested output directory,
including after an assertion failure when the guest remains accessible.

This is a headless guest probe, not a Hyprland/Chrome response measurement.
The guest does not run the host's `agentctl-pressure.service`; its loaded
30-second completion criterion remains separate. This isolates the earlyoom fallback with a scaled guest-only memory.high
fixture. After at most 30 seconds of actual memory-full PSI warmup at
900 MiB, the fixture raises its memory.high to 1000 MiB and records kernel
readback, timestamp and victim identity. Failure to reach real warmup pressure
is a failed test. It omits production scoped oomd and the full desktop protections,
so a stalled guest above the emergency RAM floor does not establish a
production-policy regression. No production policy is changed by this test.
