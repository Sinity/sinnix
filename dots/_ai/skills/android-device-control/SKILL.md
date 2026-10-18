---
name: android-device-control
description: Control, configure, debloat, or capture from the rooted Android phone (Evolution X, Magisk) through adb, root shell, Termux, tailnet access, and resilient UI automation.
metadata:
  short-description: The rooted Android phone as a controllable peer
---

# Android device control

The phone is a Redmi Note 11 NFC running Evolution X (Android 16),
bootloader-unlocked and rooted with Magisk. `docs/phone.md` in Sinnix covers
the capture app and the `sinnix phone` commands; device history and evidence
live in bead `sinnix-uyvt`. Verify the current device, OS and connection
before applying anything below.

## Control surfaces

| Surface                         | Reach                    | Good for                                         |
| ------------------------------- | ------------------------ | ------------------------------------------------ |
| `adb` (USB or wireless debugging) | USB, trusted Wi-Fi, tailnet | packages, settings, input, screenshots, UI dumps |
| root shell (`adb shell su -c ...`) | wherever adb reaches    | system files, services, Magisk hooks             |
| Termux `sshd` (:8022)           | tailnet                  | a real shell for scripted work                   |

Use the existing USB or wireless-debugging connection; `sinnix phone
adb-connect` finds it and `sinnix phone adb-restore` re-enables it over USB.
Never enable legacy `adb tcpip 5555`: it listens on every network. Select the
device with `ANDROID_SERIAL` or `adb -s` and check its identity before a
change.

Root is available through Magisk (`su -c`). Prefer an unprivileged route when
one exists, and say when a change needs root. Persistent root changes go in
Sinnix-owned Magisk hooks under `/data/adb/service.d/` so they can be listed
and removed; do not edit system partitions.

Never start Termux daemons through `adb shell run-as com.termux`: they land in
an SELinux domain that cannot read `/storage` yet reports success. Restart the
Termux app instead. Termux and its add-ons must all come from the same source
(F-Droid or GitHub builds), since their signatures must match; the Play Store
build cannot install Termux:API.

## UI automation that works

Never tap fixed coordinates; layouts shift with locale, font scale and
wrapping. Find the element in a UI dump:

```bash
adb shell "uiautomator dump /sdcard/.ui.xml >/dev/null 2>&1"
adb shell cat /sdcard/.ui.xml | tr '>' '\n' \
  | grep -E 'text="Install"' \
  | grep -oE '\[[0-9]+,[0-9]+\]\[[0-9]+,[0-9]+\]' | head -1 \
  | awk -F'[][,]' '{print int(($2+$5)/2), int(($3+$6)/2)}'
```

Tap once, then poll state (`pm list packages`, a dump) without tapping: a loop
that re-taps while waiting can hit the button that replaced the original, such
as Cancel. Check which activity is in front before acting
(`adb shell dumpsys window | grep mCurrentFocus`); an intent can be taken by a
different app than intended.

## Background apps

Android may stop long-running apps. Whitelist from Doze and keep the app in
the active standby bucket:

```bash
adb shell dumpsys deviceidle whitelist +<pkg>
adb shell am set-standby-bucket <pkg> active
```

Tailscale stays connected through always-on VPN
(`settings put global always_on_vpn_app com.tailscale.ipn`). Keep lockdown as
the operator set it; it trades offline use for blocking traffic outside the
VPN. `am force-stop` does not test background survival: Android never restarts
a force-stopped app.

## Settings worth knowing

| Setting                                                        | Why it matters                                             |
| -------------------------------------------------------------- | ---------------------------------------------------------- |
| `global audio_safe_volume_state`                               | `3` = EU headphone volume cap active; `1` disables it.     |
| `global bluetooth_disable_absolute_volume`                     | Common cause of very quiet Bluetooth headsets.             |
| `system screen_off_timeout`, `global stay_on_while_plugged_in` | A phone kept awake on AC is reliably drivable.             |
| `global window/transition/animator_*_scale`                    | `0.5` is snappy; `0` breaks some transitions.              |
| `secure ui_night_mode 2` + `cmd uimode night yes`              | Both are needed.                                           |
| `appops set <pkg> POST_NOTIFICATION ignore`                    | Silence one app's notifications.                           |
| `appops set <pkg> GET_USAGE_STATS allow`                       | What usage-tracking apps need; often the missed step.      |

## Removing apps

`pm uninstall -k --user 0 <pkg>` removes an app for the user but keeps the
APK, so `pm install-existing <pkg>` restores it. Compare package lists against
an earlier census rather than guessing what is safe.

## Finding devices on the network

`nmap -sn` misses devices that ignore ICMP. Read the router's DHCP leases
(`ssh <router> cat /tmp/dhcp.leases`) for every device that has connected,
and `iwinfo <ap> assoclist` to tell "asleep" from "off the network". Give
devices that capture lanes target a static lease.

## Discipline

- Prove a change with a round trip: a request, transfer or observed state
  change on the device, not just the command's exit status.
- A dozing phone drops ICMP but accepts TCP; health-check with a TCP connect,
  not `ping`.
- Privacy policies, EULAs, passkeys and account linking are the operator's to
  accept; surface them instead of tapping through.
