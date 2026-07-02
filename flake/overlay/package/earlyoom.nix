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
