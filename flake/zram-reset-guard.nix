# Post-rebuild zram hygiene snippet, shared by the devshell nh wrappers and
# the flake-app rebuild commands.
#
# Heavy builds under the memory-capped build slices push pages into zram that
# nothing ever faults back in (observed 3-4 GiB stale residue per switch on
# 2026-06-12, repeatedly, with ~18 GiB MemAvailable). Reset only when the
# residue is demonstrably stale — plenty of free RAM, no memory pressure, and
# a meaningful amount parked in zram — never under genuine pressure.
# Best-effort by design: a failed or skipped reset must not fail the rebuild.
{ pkgs }:
''
  if command -v sinnix-zram-reset >/dev/null 2>&1 && [ -e /sys/block/zram0/mm_stat ]; then
    _zram_orig="$(${pkgs.gawk}/bin/awk '{print $1}' /sys/block/zram0/mm_stat 2>/dev/null || echo 0)"
    _mem_avail_kb="$(${pkgs.gawk}/bin/awk '/^MemAvailable/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)"
    _mem_full_avg10="$(${pkgs.gawk}/bin/awk -F'avg10=' '/^full/ {split($2, a, " "); print a[1]}' /proc/pressure/memory 2>/dev/null || echo 100)"
    if [ "''${_zram_orig:-0}" -gt $((512 * 1024 * 1024)) ] \
      && [ "''${_mem_avail_kb:-0}" -gt $((8 * 1024 * 1024)) ] \
      && ${pkgs.gawk}/bin/awk -v p="''${_mem_full_avg10:-100}" 'BEGIN { exit !(p < 1.0) }'; then
      echo "sinnix rebuild: resetting $((_zram_orig / 1024 / 1024)) MiB of stale zram residue" >&2
      sudo sinnix-zram-reset --yes || true
    fi
  fi
''
