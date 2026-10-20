# The phone

`dev.sinnix.phone` is the phone-side app: ambient capture, instruments, quick
input, and a remote for prime. The phone is a Redmi Note 11 NFC running
Evolution X (Android 16), bootloader-unlocked and rooted with Magisk. The app
targets API 33.

## What it does

- **Remote:** prime's status, what agents are doing, answering an agent's
  question, and the actions the hub's action API accepts.
- **Capture:** ambient audio, light and motion, notifications, location,
  Health Connect, power and thermal events.
- **Instruments:** short measurement sessions (a "Check" of two to four
  instruments, under three minutes) plus decks pushed from prime.
- **Input:** share sheet, Mark (one tap, a timestamped word), hold-to-talk.

Charts and reports stay in the hub; the app links to it.

## Where it lives

| Piece                    | Path                                                                 |
| ------------------------ | -------------------------------------------------------------------- |
| App source and packaging | github:Sinity/sinnix-phone-app (`pkg.nix`, `deps.json`); flake input |
| Desktop CLI              | `scripts/sinnix-phone` (`sinnix phone ...`)                          |
| Prime's receiving side   | `pkgs/sinnix-phone-dispatcher`, routes in `modules/services/hub.nix` |
| System-log and call pull | `modules/services/phone-logcat.nix`                                  |

## Build and install

A normal Kotlin/Compose/Gradle project; `gradle.fetchDeps` records every
dependency into `deps.json`.

```bash
nix build .#sinnix-phone-app      # unsigned APK
$(nix-build . -A packages.x86_64-linux.sinnix-phone-app.mitmCache.updateScript)
                                  # regenerate deps.json (needs network)
```

Pinned versions: `targetSdk = 33` (API 34 forbids starting a microphone
foreground service at boot, and capture must start before first unlock),
`compileSdk = 36` (required by current AndroidX), `buildToolsVersion =
"36.0.0"` (unset, the sandbox build fails misleadingly). R8 is off.
`sinnix-phone-app-install` signs with a persistent keystore at
`~/.local/share/sinnix-phone-app/keystore.jks`; a new key per build would
force uninstalls, which drop the app's grants.

## Operating it

```text
sinnix phone app-install     # build, sign, install, grant, start
sinnix phone app-status      # is capture alive and producing?
sinnix phone app-start       # restart after the app was stopped
sinnix phone app-grants      # re-apply permissions and appops
sinnix phone app-soak [s]    # watch screen/foreground/mute and measure chunks
sinnix phone logcat          # pull the system log (what the timer runs)
sinnix phone pull-ambient    # rescue chunks the app could not upload
sinnix phone ambient-audit   # decode chunks and record their levels
sinnix phone health-sync     # press Mi Fitness's Sync button (UI automation)
sinnix phone unlock [s]      # temporary maintenance unlock (see below)
sinnix phone adb-restore     # re-enable wireless debugging over USB
sinnix phone adb-connect     # connect to wireless debugging
sinnix phone nix-switch      # activate the Nix-on-Droid profile
sinnix phone chroot [cmd]    # enter the Debian arm64 chroot
```

`app-install` needs ADB over USB or the tailnet, and Android still wants the
phone unlocked for some package operations. When ADB is unavailable,
`app-status` reads the newest uploaded events instead and says which source it
used.

`app-grants` applies `RECORD_AUDIO` and `POST_NOTIFICATIONS`,
`MANAGE_EXTERNAL_STORAGE` as an appop at both package and uid scope, the Doze
whitelist, and the notification-listener binding. `RECORD_AUDIO` is left at
its default foreground mode, which a running microphone service satisfies.

Nix-on-Droid owns the routine CLI profile; the `sinnix_debian_chroot` Magisk
module provides Debian Trixie arm64 for native toolchains (`chroot-build`,
`chroot-install`, `chroot-bootstrap`, `chroot-verify`). Termux owns SSH and
Android integrations.

### Connecting

SSH to the phone uses one pinned host key (the `known_hosts` file in the phone
state directory, or `SINNIX_PHONE_KNOWN_HOSTS`) across the tailnet, mDNS and
LAN addresses; discovery checks the host key and login before remembering an
address. ADB uses the serial enrolled over USB (`adb-serial` in the phone
state directory, or `SINNIX_PHONE_ADB_SERIAL`; `SINNIX_PHONE_ADB_ENDPOINT` for
an explicit address) and finds wireless debugging through Avahi. Legacy port
5555 is never opened.

`adb-restore --persistent` installs a Magisk boot hook that re-enables
wireless debugging whenever the phone joins a trusted Wi-Fi network (it checks
every ten seconds). Delete `/data/adb/service.d/sinnix-wireless-adb.sh` to
remove it.

Tailscale stays up through Android's always-on VPN setting (lockdown off, so a
broken VPN does not cut the network). The scheduled logcat pull also restarts
Tailscale if it has died.

Do not start Termux daemons through `adb shell run-as com.termux`: they land in
an SELinux domain that cannot read `/storage` but reports success. Restart the
Termux app instead (`am force-stop com.termux`, then start
`com.termux/com.termux.app.TermuxActivity`); its profile starts `sshd`.

### Maintenance unlock

`sinnix phone unlock [seconds]` (default 60, maximum 600) temporarily disables
the lock screen through the ROM's profile service, keeping the PIN. A root
watchdog restores the lock policy when the window ends, even if the command or
ADB connection dies, and a Magisk boot hook
(`/data/adb/service.d/sinnix-keyguard-recovery.sh`) restores it after a
reboot. The phone must already have been unlocked once since boot.

## Transport

Every action in the app is a local write that the app then uploads, so the app
works offline and delivers everything when it next has a network. Files are
deleted on the phone only after prime confirms the exact bytes (size and
SHA-256). Uploads to `/phone/v1/*` go to `sinnix-phone-dispatcher` on port 8940,
tailnet only; requests carrying browser `Origin` or Fetch-Metadata headers are
refused.

| File on the phone                         | Direction | Route and destination                                 |
| ----------------------------------------- | --------- | ----------------------------------------------------- |
| `ambient-*.m4a`                           | out       | `POST /chunk?lane=ambient` → capture store            |
| `sensor-*.bin` + `.json`                  | out       | `POST /chunk?lane=outbox`                             |
| `events/events-*.jsonl`                   | out       | `POST /events?day=&offset=` → that day's file         |
| `outbox/intent-*.json`                    | out       | `POST /intent` → executed, receipt sent back          |
| `outbox/{voice,trace,shared}-*` + `.json` | out       | `POST /chunk?lane=outbox`                             |
| `/sdcard/DCIM`                            | out       | `POST /chunk?lane=camera` (`SINNIX_PHONE_CAMERA_DIR`) |
| `/sdcard/Download`                        | out       | `POST /chunk?lane=download`                           |
| `inbox/glance.json`                       | in        | built on request (`GET /inbox/file`)                  |
| `inbox/receipts/*`, `inbox/notify/*`      | in        | fetched, confirmed, shown, then deleted               |
| `inbox/decks/*`                           | in        | fetched and kept; adds instruments                    |
| `status.json`                             | read      | over ADB by `app-status`                              |
| logcat                                    | pulled    | `sinnix phone logcat` over ADB                        |
| BCR call recordings                       | pulled    | scheduled ADB pull → `phone-calls` lane               |

Retries are safe: an event batch is written at the offset it declares, a chunk
prime already has is acknowledged again, and each intent carries a token so a
repeated request returns the earlier receipt instead of acting twice. An
intent whose outcome is unclear is kept for review, never replayed
automatically. Unit actions (`start`/`stop`/`restart`) are never queued: if
prime is unreachable, the app says so instead.

Two things are still pulled by prime over ADB, because the app cannot do them:
the system log (needs `READ_LOGS`) and call recordings, which belong to the
separate BCR app. The pull runs every 30 minutes and works over USB too. Each
new call recording is decoded and its level recorded in
`/realm/device/shared/phone/calls/levels.jsonl`; a silent recording fails the
run. BCR's own staging copy is preferred over its export, which can be
truncated. The same pull warns when finished ambient chunks pile up on the
phone (capture works, upload does not).

`/sdcard/sinnix-ambient` is the upload queue: each chunk is deleted after a
confirmed upload. `/sdcard/sinnix-phone` holds the app's own events, outbox,
inbox and epoch; event files are never deleted, because they are also the
app's history.

## Ambient capture

Mono 48 kHz AAC at 96 kbps in 300 s chunks (about 3.6 MB), the same grade as
the desktop audio lanes, so the archive keeps the full band (speech
recognition works from it on prime). A microphone foreground service with a
persistent notification is the only way to record with the screen off, which is
why this is an app.

Files are named `ambient-<UTC basic ISO time>.m4a` (the storage layer rejects
colons). A chunk is written as `.m4a.part` in private storage and published only
after the muxer closes it and its duration is checked; a `.part` left by a
crashed recorder becomes `.m4a.orphan` and is still uploaded.

The app checks amplitude and file growth every 20 s. Four exact-zero
samples in a row restart the recorder. No growth for 90 s, or growth under
half the expected bitrate, also restarts it. Each closed chunk's encoded
duration is compared with elapsed time. On prime, `sinnix phone ambient-audit`
decodes every chunk into
`ambient-levels.jsonl` and flags all-zero audio.

Another app using the microphone does not stop capture (they use separate
inputs); phone calls do, by Android policy. Capture restarts on app open, on a
10-minute alarm, through `START_STICKY`, and at boot. Stopping capture in the
app is remembered, so the watchdog does not undo it.

A direct-boot-aware service records into device-protected storage before the
first unlock and moves the data after unlock. That buffer is capped, so a very
long locked period drops its oldest audio.

The capture, grants and transport screens grade each source as **evidenced**,
**unverified** or **broken**; nothing is shown as OK without a measurement
behind it. The grants screen tests storage access by writing a real file.

The sensor lane records raw accelerometer and light readings continuously in
five-minute binary chunks (`sinnix.phone.sensor-binary/1`) with their
timestamps; a minute-level `ambient_context` event summarizes them.

## Instruments

A Check is chosen by policy, not from a menu: a PVT if none in the last twelve
hours, then instruments for hours never sampled, then the stated energy level;
auditory instruments only with headphones. Five engines (reaction, forced
choice, staircase, hold-still, counting) run every instrument; a deck from
prime names an engine and its settings, so new instruments need no app
release. A deck for an unknown engine is shown as not runnable.

Reaction timing uses the presented frame's timestamp and the touch event's
hardware time, minus the calibrated touch latency when there is one. An
"epoch" is the build fingerprint plus that calibration; results compare only
within an epoch. Interrupted trials are discarded and repeated. Auditory
staircases play both intervals from one audio buffer, so device latency
cancels out.

The phone timestamps and records raw signals; prime does the scoring
(`scripts/sinnix-score`) and sends receipts back.

Deliberately not built: screen-based flicker fusion and contrast sensitivity
(the display is not a calibrated light source), pupillometry and saccades
(need a vision model), n-back and digit span (practice effects dominate).
Torch-based flicker fusion first measures whether the torch can switch fast
enough.

## Input

- **Share sheet:** URLs, text, images and PDFs go into the outbox. Shared
  `content://` files are copied immediately, because the read grant expires.
  This is also the way to send phone clipboard text to the desktop.
- **Mark:** one tap from a tile, widget or sheet records a timestamped word.
- **Talk:** hold to record on a second recorder; ambient capture keeps
  running. Transcription happens on prime.
- **Notifications:** a notification listener logs posted and removed
  notifications, and its own binding changes, as events.

## Other phone lanes

- **Location** from the framework fused provider, with geofence transitions.
- **Health Connect**, read directly by the app.
- **Power and thermal** events (`thermal_headroom` is null on this device,
  which does not implement it).
- **Sleep estimate** from motion, light, screen and charging.
- **Xiaomi cloud** band data, independent of Health Connect: `sinnix
capture-xiaomi-cloud` syncs once; `sinnix xiaomi-cloud-login` prints a
  `LOGIN_URL` to confirm in a logged-in browser after the credential expires.
  Runs overlap seven days; `agentctl job start sinnix xiaomi_cloud_backfill`
  covers 35 days after an outage.

## Continuity

- **Desktop → phone clipboard:** `sinnix phone clip-push` sends the desktop
  CLIPBOARD (text only) to the phone; `sinnix-phone-clip-watch.service` does it
  on every change.
- **Phone → desktop clipboard:** Android blocks background clipboard reads;
  use the share sheet. Android has no PRIMARY selection.
- **Phone → desktop notifications:** the dispatcher shows each newly uploaded
  phone notification on the desktop, skipping ongoing ones.
- **Desktop → phone notifications:** `sinnix-phone-dispatcher notify TITLE
BODY [--route R]` queues one; nothing sends them automatically yet.

Whether KDE Connect should take over commodity continuity is open in
`sinnix-z8iq.5`; remaining continuity work is `sinnix-uyvt.5`.

## Local models over the tailnet

With Tailscale up, open `http://sinnix-prime:8881/`; Open WebUI starts on the
first request. Inference runs on the workstation; the phone is only a browser. See
[local AI activation](local-ai-activation.md#open-webui).

## Known limits

- Media mirroring resumes from the newest acknowledged file; files that appear
  later with older timestamps need an explicit rescan.
