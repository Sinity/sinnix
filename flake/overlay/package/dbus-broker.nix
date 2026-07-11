# Two shutdown-robustness fixes submitted upstream (sinnix-not, 2026-07-11
# incident: broker died at shutdown start when a diagnostic raced journald
# teardown, the launcher then kept the unit alive with a dead broker, and
# PID 1 serialized the remaining shutdown behind 90s bus-reconnect blocks):
#  - util/log: journal-unavailable send failures must drop in lossy mode,
#    not escalate into a fatal broker error.
#  - launch: exit on broker child death even when the SIGCHLD diagnostic
#    cannot be committed.
#
# recheck: drop whichever patch has landed when nixpkgs ships a dbus-broker
# release containing the upstream PRs.
_: _final: prev: {
  dbus-broker = prev.dbus-broker.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [
      ./dbus-broker-lossy-log-journal-unavailable.patch
      ./dbus-broker-launch-exit-on-child-death.patch
    ];
  });
}
