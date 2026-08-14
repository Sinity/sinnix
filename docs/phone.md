# The phone

`dev.sinnix.phone` — the estate's phone-side member. Ambient capture,
instruments, ingress, and a remote for prime, on a Redmi Note 11 (Android 13 /
API 33, unrooted, bootloader locked, MIUI).

It began as an answer to one platform constraint and outgrew it. That history
still matters in one place — the capture surfaces, where it is the reason they
look the way they do — and nowhere else.

## What it is for

Four things, and they are peers:

- **The estate remote.** The verdict, what agents are doing, answering an
  agent's question, and the bounded actions the hub's action API accepts.
- **Capture.** Ambient audio, ambient light and motion, notifications — the
  lanes only a device in a pocket can produce.
- **Instruments.** A Check of two to four measurements under three minutes,
  plus a shelf, plus decks pushed from prime.
- **Ingress.** Share-sheet, the Mark verb, hold-to-talk: getting something out
  of the phone and into the lake in under three seconds.

It is deliberately **not** a dashboard. The hub renders charts, logs and
reports well and is already reachable over the tailnet; the Estate screen deep
links out to it rather than repeating it.

## Where it lives

| Piece | Path |
| --- | --- |
| App source | `pkgs/sinnix-phone-app/app/src/main/` |
| Build + install packaging | `pkgs/sinnix-phone-app/pkg.nix`, `deps.json` |
| Desktop control surface | `scripts/sinnix-phone` |
| Prime's half of the transport | `scripts/sinnix-phone-dispatcher` |
| Steering export for the phone | `scripts/sinnix-steer export-phone` |
| Scheduled bidirectional drain | `modules/services/phone-drain.nix` |
| Live-plane route + unit | `modules/services/hub.nix` (`/phone/v1/*`) |

## Build

A normal Android project — Kotlin, Compose, AndroidX, Gradle — made
reproducible the way nixpkgs supports: the Gradle setup hook drives the build
and `gradle.fetchDeps` records every artifact fetch through `mitm-cache` into
the committed `deps.json`.

This replaced a deliberately Gradle-free build (aapt2 + javac + d8 called
directly, zero dependencies, views constructed in code). That build was correct
for an app with nothing to resolve, and wrong once the app needed an interface:
hand-rolling framework views to avoid a dependency lock is a permanent
interface cost paid to avoid a one-time build cost.

```
nix build .#sinnix-phone-app            # the unsigned APK
$(nix-build . -A packages.x86_64-linux.sinnix-phone-app.mitmCache.updateScript)
                                        # regenerate deps.json after a dependency change
```

The update script needs network and runs outside the sandbox; the ordinary
build does not and cannot reach it.

Three version pins, each for a stated reason:

- **`targetSdk = 33`.** API 34 forbids starting a microphone foreground service
  from a `BOOT_COMPLETED` receiver, and resuming capture after a reboot without
  the operator touching anything is a standing acceptance criterion. Raising it
  needs a Direct Boot design first, not a version bump.
- **`compileSdk = 35`.** Current AndroidX refuses to be compiled against
  anything older. Unrelated to `targetSdk`, which is a behaviour opt-in.
- **`buildToolsVersion = "35.0.0"`.** AGP 8.10's floor. Left unset, AGP picks
  its own default and the sandbox fails with a missing-component error that
  reads like a network problem.

The APK is emitted **unsigned**; `sinnix-phone-app-install` signs it against a
keystore at `~/.local/share/sinnix-phone-app/keystore.jks`, created once and
persisted. A key regenerated on every source change would make each
`adb install -r` fail with a signature mismatch and force an uninstall, which
on Android also discards the app's runtime grants.

R8 is off. Shrinking buys a few hundred KB on a sideloaded app and costs a
class of reflection surprises that would only ever appear on the one device
that matters.

## Operating it

```
sinnix phone app-install    # build, sign, sideload, grant, start
sinnix phone app-status     # is capture alive AND producing?
sinnix phone app-start      # relaunch after the app was stopped
sinnix phone app-grants     # re-assert shell-uid grants
sinnix phone app-soak [s]   # acceptance test: screen/foreground/mute + chunk measurement
sinnix phone drain          # the bidirectional sync, wifi-gated
sinnix phone push           # send prime's half now, without pulling
```

`app-install` needs adb over USB or the tailnet, **and the phone must be
unlocked**. MIUI routes every adb install through its own
`com.miui.permcenter.install.AdbInstallActivity` confirmation dialog, which
cannot be shown over the keyguard; the install is then auto-cancelled with
`INSTALL_FAILED_USER_RESTRICTED`. There is no desktop-side workaround.

Grants applied by `app-grants`: `RECORD_AUDIO` and `POST_NOTIFICATIONS` as
runtime permissions, `MANAGE_EXTERNAL_STORAGE` as an appop at **both** package
and uid scope, and the Doze whitelist. The two appop scopes are set separately
because only one of them reverting is exactly what broke capture before.

`RECORD_AUDIO` is deliberately *not* forced to appop `allow`. The default
`MODE_FOREGROUND` is already satisfied while a microphone-typed foreground
service is up — measured clean on 2026-08-13, uid mode `foreground` with the op
reading `allow; running` and no package-scope override anywhere. Overriding it
would mask a service regression rather than fix one.

## The two planes

Every verb the app offers works through **files**, and the tailnet only removes
the wait. That is the whole architecture, and it is why the app is usable on a
device that spends most of its life unreachable.

**File plane.** The app writes into `/sdcard/sinnix-phone/outbox/`; the drain
collects it and hands it to `sinnix-phone-dispatcher dispatch`. The drain also
pushes `/sdcard/sinnix-phone/inbox/` down — `glance.json`, `steering.json`,
receipts, notifications, decks. Latency is the drain interval (1800s, wifi
gated).

**Live plane.** One HTTP client speaking JSON to `/phone/v1/*` on the hub. The
payloads are byte-identical to the file plane's, and one implementation on
prime executes both — if the live path had its own logic the two would drift,
and the drift would present as "it worked when I was home", which is the least
debuggable class of bug.

Reachability is **measured, not assumed**: the app pings, renders the
round-trip and its age ("live · 34 ms"), and every action reports the path it
actually took — `sent · live` or `queued · next drain`.

Idempotency is the `send_token`. The drain can legitimately deliver the same
intent twice, and an intent that also went out live arrives again by design;
prime records every executed token, and a repeat is a no-op that still emits
its receipt.

**Actions are the one thing never queued.** `start`/`stop`/`restart` on a live
unit is a decision about right now; executing it half an hour later against a
machine nobody looked at is a different and worse action than the one that was
asked for. The Estate screen says so instead of offering a button that would
lie.

### Contracts

| File | Direction | Writer → reader |
| --- | --- | --- |
| `ambient-*.m4a` | out | AmbientService → drain → lake |
| `status.json` | out | app → `app-status`, tile, capture screen |
| `events/events-*.jsonl` | out | every screen → drain → lake |
| `outbox/intent-*.json` | out | app → drain → dispatcher |
| `outbox/{voice,trace,shared}-*` + `.json` | out | app → drain → lake |
| `epoch.json` | local | instruments only |
| `inbox/glance.json` | in | dispatcher → drain → home + widget |
| `inbox/steering.json` | in | `sinnix-steer export-phone` → drain → steering trio |
| `inbox/receipts/*.json` | in | dispatcher → notification, then deleted |
| `inbox/notify/*.json` | in | estate → notification, then deleted |
| `inbox/decks/*` | in | prime → the instrument shelf |

The two device directories are deliberately separate. `/sdcard/sinnix-ambient`
has exactly one meaning to the drain — audio, rotated and deleted once the lake
holds it — and `--remove-source-files` pointed at an event log is a data-loss
bug waiting for its first drain.

## Capture

Mono 48 kHz AAC at 96 kbps, 300s chunks (~3.6 MB), the same archive grade the
desktop lane encodes at, so a phone chunk and a desktop chunk are the same
class of evidence. This is an archive lane, not a speech-recognition feed:
16 kHz caps audio bandwidth at 8 kHz and discards the room — music,
environment, the timbre diarization and speaker identification depend on —
before anything is written, and nothing downstream recovers a band that was
never captured.

`foregroundServiceType="microphone"` with a persistent notification is the only
supported way to hold the microphone with the screen off on modern Android, and
it can only be declared in an app's manifest. That single capability is why
this is an app rather than the Termux script it replaced — a script that
truncated chunks (mean 148s against an expected 300s) and never survived a
reboot.

Files are `ambient-<UTC ISO basic>.m4a`. The compact stamp is not a style
choice: sdcardfs rejects colons outright, so an extended-ISO filename fails
every open with EPERM while the recorder looks healthy. The file being written
is `*.m4a.part` and is renamed only after the muxer closes it, because the
drain rsyncs with `--remove-source-files` and would otherwise delete the open
file and lose its trailing `moov` atom.

A `.part` found at service startup belongs to a recorder that died without
closing its muxer; those are renamed to `*.m4a.orphan`, which the drain *does*
collect. Renamed rather than deleted: an MP4 without its `moov` atom is not
playable but the samples are still there, and discarding captured audio is not
the device's call.

### Failure impersonates success

Every serious failure this program has hit had the same shape:

| Failure | What "healthy" looked like |
| --- | --- |
| Termux truncation | chunks landed every 5 min (148s of audio inside) |
| Reboot death | all visible policy state survived; capture didn't |
| Arbitration mute | perfect duration, full bitrate, valid container — digital silence |
| MIUI grant revocation | no event, no error, discovered at the next failure |

Exception-driven error handling is structurally blind here: nothing throws. So
the app judges itself by evidence of the product rather than health of the
process, at three cadences:

- **Amplitude, every 20s.** A live microphone in a silent room still reports
  its own noise floor, so a run of *exact* zeroes means muted rather than
  quiet. Four consecutive zero samples (80s) cycles the recorder.
- **File growth, every 20s.** A chunk file that has not grown for 90s means the
  recorder stopped producing frames while still believing it is running.
- **Decoding, at intake.** `sinnix phone ambient-audit` decodes every chunk as
  it lands into `ambient-levels.jsonl` with duration, rate, mean and peak,
  flagging the −91 dB a stream of exact zeroes decodes to. Run against the
  Termux-era lake it found 29 of 111 chunks had captured nothing and 14 more
  did not decode at all.

Detection is not prevention. If Android's concurrent-capture arbitration
decides a foreground app wins, cycling the recorder may not take the microphone
back. Measured 2026-08-13, though: another app using the microphone does **not**
stop this one — the camera's `AUDIO_SOURCE_CAMCORDER` client took the back mic
while this service held the bottom mic, both `State: Active` on separate input
ports, amplitude unchanged. Phone calls remain a hard stop; Android has blocked
third-party call-audio capture since Android 10.

### Keepalive, cheapest first

The 20s heartbeat self-heals audio failures in seconds. Opening the app
restarts a dead service immediately. A 10-minute inexact alarm covers process
death. `START_STICKY` covers the platform's own low-memory path. `BootReceiver`
covers reboots.

Stopping capture from the capture screen flips the persisted intent bit, so the
watchdog respects it — without that the button would be a lie, resurrecting
capture ten minutes later.

## Trust grading, and where it stops

Three grades — **evidenced / unverified / broken** — with one rule: nothing
reaches evidenced without a measurement to name, and anything unverifiable
stays unverified rather than being rounded up to OK.

They appear on the capture screen, the grants screen and the transport label,
and nowhere else. That boundary is deliberate. Those are the surfaces where
"measured OK" and "assumed OK" are genuinely different claims; putting
reliability vocabulary on home, the bench, the estate remote or Talk would make
dev-time incident history the subject of a tool whose subject is capture,
measurement and action.

The grants screen writes a real probe file rather than trusting
`isExternalStorageManager()` — the API has returned true on this device while
`/sdcard/sinnix-ambient` was not writable, and the difference between those two
facts is every chunk recorded somewhere Termux cannot read. MIUI autostart has
no API at all, so it renders as permanently unverifiable with two weaker things
shown in place of a check: an operator attestation with its date, and an
inference from the log (a boot with no chunk after it is evidence autostart is
off).

## Instruments

The unit is the **Check** — two to four instruments, under three minutes,
assembled by an offer policy rather than chosen from a menu. A flat catalogue
of twenty is a compliance disaster: choosing is work, and work at the moment of
measurement is what stops the measurement happening. The **shelf** exists
behind it precisely so the policy can stay opinionated.

Offer policy, in order of authority: the PVT if none in twelve hours; then
instruments whose covariate cells are empty (a measurement at an hour never
sampled is worth more than the fifth one at 21:00); then the declared energy
state; and never an auditory instrument without headphones — it is not in the
deck at all rather than offered and refused.

**Five engines cover everything**, and an instrument is a *configuration* of
one: reaction, forced choice, staircase, hold-still, counting. That is what
makes decks possible — prime writes JSON into `inbox/decks/`, the shelf gains
an instrument, and no app release happens. A deck names an engine and a version;
an unknown one renders as present-but-not-runnable with the reason shown,
because a deck that silently did something approximate would produce data that
looks like the real instrument and is not.

Three timing decisions carry the reaction engine, and none is optional: the
stimulus is timestamped in a `Choreographer` frame callback (when the frame was
*presented*, not when composition asked); the response is
`MotionEvent.getEventTime()` (the digitizer's clock, not the handler's); and
the epoch's touch offset is subtracted only if calibrated, with the record
saying which. Two fingers discard a trial. `onPause` mid-trial discards and
re-presents at the same position — a call during a PVT is not a slow response —
and the run carries an `interruptions` count.

The **apparatus epoch** is `Build.FINGERPRINT` plus the measured touch-latency
calibration. Results are comparable only within an epoch; a fingerprint change
opens a new one and never inherits the old offset, because the offset is
exactly what a firmware change moves.

**Phone owns stimulus timing and raw signal; prime owns scoring.** Anything the
phone can compute from its own event stream shows a number immediately;
anything needing a model ships a trace and gets a receipt. That falls out of not
shipping ML and is the right architecture anyway — a live heart-rate readout
would invite exactly the realtime self-steering this design excludes.

Cut, with reasons: **panel-based CFF and contrast sensitivity** (the display is
not a photometric instrument, and a 120 Hz panel puts a 60 Hz ceiling exactly
where foveal CFF sits); **pupillometry and saccades** (face landmarks means a
model); **n-back and digit span** (practice effects dominate, so repeated
measurement measures learning). Torch-driven CFF survives the panel objection
and measures its own feasibility first — `setTorchMode` is a binder round trip,
so the instrument records the switch cost and the achievable ceiling either way
before any threshold is claimed.

Auditory staircases survive an uncalibrated device for a specific reason worth
generalising: **both intervals are rendered into one PCM buffer and played
once**, so the measurand is a difference internal to that buffer and every
latency affects both identically and cancels. Prefer measurands that are
internal differences.

## Ingress

- **Share sheet.** One manifest entry makes the app a target in every share
  sheet: URLs, text, images, PDFs land in the outbox and drain like anything
  else. It is also the sanctioned workaround for Android's
  background-clipboard-read ban — sharing is push-shaped and always allowed,
  which gets the phone→desktop direction without an AccessibilityService.
  Shared `content://` URIs are *copied*, not referenced: the permission grant
  dies with the Activity, and a drain half an hour later would find nothing.
- **Mark.** One tap, a timestamped word, three-second budget from a cold phone
  — hence a sheet rather than a screen, a tile, and a widget button. The
  cheapest capture in the design and the one that multiplies everything else at
  join time: a reaction-time series is a curve, and the same series with
  caffeine doses on it is a dose–response curve.
- **Talk.** Hold to record, on a second `MediaRecorder` running concurrently
  with ambient capture (measured: two clients, separate input ports, no loss).
  Ambient is not paused, because a note is the moment you would least want a
  hole. No on-device transcription — prime's engine is better and the receipt
  pattern avoids realtime self-steering.
- **Notifications.** A `NotificationListenerService` logs post and dismiss into
  the events plane: the inbound comms timeline nothing else in the estate can
  produce. MIUI may revoke the binding silently, so connect and disconnect are
  written as events and a gap explains itself.

## Known limits

- **Reboot resumes at first unlock, not at power-on.** The device uses
  file-based encryption with a screen lock, so `BOOT_COMPLETED` arrives after
  the first unlock and `/sdcard` is not mounted before it. No app has to be
  opened and nothing tapped, but a phone left locked after a reboot is not
  capturing. Making this truly unattended needs Direct Boot handling: a
  `directBootAware` service buffering into device-protected storage.
- **MIUI background autostart has no adb assertion path.** The watchdog alarm
  and `START_STICKY` cover process death; they do not cover MIUI refusing to
  deliver the boot broadcast at all. The screen that owns it is driveable —
  `com.miui.securitycenter/com.miui.permcenter.autostart.AutoStartManagementActivity`
  — but `uiautomator dump` can return a **stale window**, so cross-check against
  `dumpsys window | grep mCurrentFocus` and trust a screenshot over a dump when
  they disagree; the list also re-sorts after every toggle, so coordinates must
  be re-derived rather than reused.
- **Phone calls stop capture.** Platform decision since Android 10, not a
  configuration gap.
- **The steering ready queue is approximated.** Until the steering store grows
  its own queue table, `export-phone` treats open commitments whose window ends
  today as the ready set.

## Keeping the phone reachable

The tailnet had been failing because Tailscale simply was not running and
nothing restarted it. Doze-whitelisting prevents it being *dozed*; it does not
start it. Two things fix that and both are set: Android always-on VPN
(`settings put global always_on_vpn_app com.tailscale.ipn`, lockdown
deliberately off — with it a phone whose VPN is down has no network at all),
and MIUI background autostart for Tailscale.

`am force-stop` is not a test of either. Android deliberately never restarts a
force-stopped app, so the case that matters — a reboot, or MIUI reclaiming the
process — is not what force-stop reproduces.

adbd's TCP mode does not survive a reboot; `sinnix phone adb-restore` re-enables
it over USB. Everything the app does is designed around that: `status.json` is
read over whichever adb transport is up, USB included, so liveness never
depends on Termux, sshd, or the tailnet — precisely the layers that kept
failing.
