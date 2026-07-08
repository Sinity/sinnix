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
_: _final: prev: {
  earlyoom = prev.earlyoom.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [
      ./earlyoom-physical-memtotal-percent.patch
    ];
    passthru = (old.passthru or { }) // {
      sinnixUsesPhysicalMemTotalPercent = true;
    };
  });
}
