{ lib }: {
  # PAM login limits factory
  # Usage: mkPAMLimits { domain = "@audio"; rtprio = 95; memlock = "unlimited"; }
  mkPAMLimits = { domain, rtprio ? null, memlock ? null, nice ? null }:
    lib.concatLists [
      (lib.optional (rtprio != null) {
        inherit domain;
        type = "-";
        item = "rtprio";
        value = toString rtprio;
      })
      (lib.optional (memlock != null) {
        inherit domain;
        type = "-";
        item = "memlock";
        value = memlock;
      })
      (lib.optional (nice != null) {
        inherit domain;
        type = "-";
        item = "nice";
        value = toString nice;
      })
    ];
}
