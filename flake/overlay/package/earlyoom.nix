# recheck: this patch reverts earlyoom's deliberate design (meminfo.c uses
# UserMemTotal = MemAvailable + AnonPages, not physical MemTotal, precisely
# so cgroup/tmpfs-constrained memory is measured correctly — see
# rfjakob/earlyoom#82) back to physical MemTotalKiB for the percent
# calculation. Upstream is unlikely to ever adopt this as the default, so
# there is no "wait for upstream to fix it" condition. Recheck only if (a)
# sinnix's cgroup/slice memory policy changes such that UserMemTotal-based
# percentages would be correct again, or (b) nixpkgs bumps earlyoom past
# 1.9.0 and meminfo.c is restructured enough that this line-based patch
# fails to apply (loud failure, not silent staleness).
#
# The psi-gate patch adds --mem-psi-min: a third conjunction term that only
# permits kills while memory PSI "full avg10" is at or above the given value
# (fail-open when pressure data is unavailable; EARLYOOM_PSI_PATH is a test
# hook). Measured basis (2026-08-18 incident taxonomy, sinnix-miop): 84% of
# post-2026-07-13 earlyoom kills happened at memory PSI < 10 — the machine
# was not stalling, page cache and swap were absorbing the burst as designed.
# Upstream earlyoom 1.9.0 is deliberately meminfo-only and carries no PSI
# support, so this is a local patch with the same recheck condition (b) as
# above. Applies on top of the physical-memtotal patch; regenerate both
# together on an earlyoom bump.
_: _final: prev: {
  earlyoom = prev.earlyoom.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [
      ./earlyoom-physical-memtotal-percent.patch
      ./earlyoom-psi-gate.patch
    ];
    passthru = (old.passthru or { }) // {
      sinnixUsesPhysicalMemTotalPercent = true;
      sinnixHasPsiGate = true;
    };
  });
}
