# Two shutdown-robustness fixes submitted upstream (sinnix-not; PR
# https://github.com/bus1/dbus-broker/pull/457). Root cause: a full journald
# restart (socket units included) permanently orphans every already-connected
# journal client - next send ECONNREFUSED, every later one ENOTCONN, journal
# itself unaffected. The broker's next lossy diagnostic (routinely emitted at
# shutdown teardown) then killed the broker, and the launcher survived its
# dead child, leaving a zombie unit:
#  - util/log: journal-unavailable send failures must drop in lossy mode,
#    not escalate into a fatal broker error.
#  - launch: exit on broker child death even when the SIGCHLD diagnostic
#    cannot be committed.
#
# recheck: drop whichever patch has landed when nixpkgs ships a dbus-broker
# release containing the upstream PR.
_: _final: prev: {
  dbus-broker = prev.dbus-broker.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [
      ./dbus-broker-lossy-log-journal-unavailable.patch
      ./dbus-broker-launch-exit-on-child-death.patch
    ];
  });
}
