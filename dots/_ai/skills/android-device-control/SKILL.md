---
name: android-device-control
description: Control, configure, debloat, or capture from an unrooted Android phone through adb, Termux, tailnet access, and resilient UI automation, including Xiaomi power-management traps.
metadata:
  short-description: Unrooted Android as a controllable peer
---

# Android device control (unrooted)

Verified live on the operator's unrooted Xiaomi device; where a claim is
inferred it says so. Device-specific facts (model, tailnet address) live in
bead `sinnix-uyvt` — read it, don't assume them from here.

## The two control surfaces

A phone worth controlling has **both**, because each covers the other's gaps:

| Surface                           | Reach            | Good for                                       | Dies when                       |
| --------------------------------- | ---------------- | ---------------------------------------------- | ------------------------------- |
| `adb` over TCP (`adb tcpip 5555`) | any tailnet peer | packages, settings, input, screencap, UI dumps | phone reboots (TCP mode resets) |
| Termux `sshd` (:8022)             | any tailnet peer | real shell, rsync, scripted work               | Termux is killed or uninstalled |

`adb tcpip` binds all interfaces, so it rides the tailnet with no extra work —
this is the single highest-leverage move for remote phone control. Two adb
transports (USB + TCP) coexist; disambiguate with `ANDROID_SERIAL`, not
`adb -s` (the latter breaks when callers build command strings).

## UI automation that actually works

Never tap fixed coordinates. Layouts shift with title wrapping, locale, and
font scale — a hardcoded tap silently hits the wrong control.

```bash
adb shell "uiautomator dump /sdcard/.ui.xml >/dev/null 2>&1"
adb shell cat /sdcard/.ui.xml | tr '>' '\n' \
  | grep -E 'text="Install"' \
  | grep -oE '\[[0-9]+,[0-9]+\]\[[0-9]+,[0-9]+\]' | head -1 \
  | awk -F'[][,]' '{print int(($2+$5)/2), int(($3+$6)/2)}'
```

**The polling-tap trap** (cost real time to find): a loop that re-taps while
waiting for an install to finish will _cancel_ it — the button under that
coordinate becomes CANCEL once the dialog advances. Tap once, then poll with
`pm list packages` only. Never tap inside a wait loop.

Read state before acting: `adb shell dumpsys window | grep mCurrentFocus`
tells you which activity is actually foreground, which is how you notice that
your intent was hijacked by a different app (a `VIEW` intent for an APK MIME
type went to Termux, not the installer).

## MIUI / HyperOS traps

**Installing apps.** There are _two_ independent blockers, and conflating them
wastes hours:

1. **Package verifier** — makes the installer hang forever on "Installing…".
   `settings put global package_verifier_enable 0` and
   `verifier_verify_adb_installs 0` clear it.
2. **The MIUI gate proper** — `adb install` of a _genuinely new_ package
   returns `INSTALL_FAILED_USER_RESTRICTED` regardless of the verifier.
   Reinstalling an app that already exists succeeds. No user restriction is
   set (`dumpsys user` shows none) — it is HyperOS's own Mi-account-gated
   "Install via USB" developer toggle. **Ask the operator to flip it**; it is
   60 seconds of their time and unblocks everything unattended.

MIUI also interposes `com.miui.permcenter.privacymanager.SpecialPermissionInterceptActivity`
("Danger / Install dangerous apps") _before_ the system installer. Expect a
two-dialog sequence: MIUI OK → system INSTALL.

**Background killing.** MIUI kills long-running apps aggressively. In escalating
order of effectiveness:

```bash
adb shell dumpsys deviceidle whitelist +<pkg>      # necessary, not sufficient
adb shell am set-standby-bucket <pkg> active       # necessary, not sufficient
adb shell settings put secure miui_optimization 0  # helps, wants a reboot
adb shell settings put secure always_on_vpn_app com.tailscale.ipn   # THE fix for a VPN
```

For a VPN specifically, **always-on VPN is the only thing that held**. The
first three left Tailscale dropping every 5–10 minutes. Leave
`always_on_vpn_lockdown` at `0` — lockdown kills all traffic whenever the
tunnel is down, the wrong trade for a phone.

**Play-store Termux is crippled**: it cannot install Termux:API
(termux-play-store/termux-apps#29). `termux-battery-status` works from a
bundled subset; `termux-sensor` and most of the 69-command API surface refuse.
The F-Droid/GitHub build is required for the sensor plane — and the app and
its addons must come from the _same_ source, since signatures must match.

## Settings levers worth knowing

| Setting                                                        | Why it matters                                                               |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `global audio_safe_volume_state`                               | `3` = EU headphone cap ACTIVE — max slider still sounds quiet. `1` disables. |
| `global bluetooth_disable_absolute_volume`                     | Common cause of very quiet BT headsets.                                      |
| `system screen_off_timeout`, `global stay_on_while_plugged_in` | Keeping a phone awake on AC is what makes it reliably drivable.              |
| `global window/transition/animator_*_scale`                    | `0.5` is the snappiness sweet spot; `0` breaks some transitions.             |
| `secure ui_night_mode 2` + `cmd uimode night yes`              | Both, not either.                                                            |
| `appops set <pkg> POST_NOTIFICATION ignore`                    | Per-app notification kill without touching the app.                          |
| `appops set <pkg> GET_USAGE_STATS allow`                       | What ActivityWatch-class apps actually need; usually the missed step.        |

## Debloating without breaking things

`pm uninstall -k --user 0 <pkg>` is the right verb: removes for the user,
keeps the APK, reversible with `pm install-existing`. For genuine third-party
apps `pm uninstall --user 0` is fine.

Two rules learned the hard way:

- **Spare the unlock stack.** On Xiaomi, keep `com.xiaomi.account`,
  `com.xiaomi.finddevice`, and the cloud services — bootloader unlock requires
  a linked Mi account and Find Device. Removing them forecloses rooting later.
- **Prefer evidence over vibes.** Diff the _previous phone's_ package census
  against the current device to find orphans; a device switch strands whole
  vendor stacks.

Unambiguously safe MIUI removals: `com.miui.msa.global` (the ad engine),
`com.miui.analytics`, `com.xiaomi.mipicks`, `com.mi.globalminusscreen`
(App Vault), `com.miui.android.fashiongallery` (lockscreen ads),
`com.xiaomi.ugd`, `com.miui.cleaner`, `com.miui.yellowpage`.

## Finding devices on the network

`nmap -sn` misses IoT endpoints that do not answer ICMP while serving HTTP
happily. **Read the router's DHCP lease table instead** (`ssh <router> cat /tmp/dhcp.leases`): it lists every
device that ever connected, with MAC and hostname, including ones currently
asleep. To tell "asleep" from "off-network", check association directly:
`iwinfo <ap> assoclist` per AP — a device with a lease but no association is
not on wifi at all.

Pin IoT devices to static leases once found. A capture lane that targets an IP
breaks silently when DHCP moves the device.

## Discipline

- **Prove it with a round-trip.** "Installed" is not "working". Every claim
  here was verified by an actual request, transfer, or observed state change.
- **A dozing Android drops ICMP but accepts TCP.** Health-check a phone with a
  TCP connect, never `ping` — otherwise you report a false outage on a working
  link.
- **Legal acceptances are the operator's.** Privacy-policy and EULA dialogs,
  passkey enrollment, and account linking are identity acts; surface them
  rather than tapping through.
