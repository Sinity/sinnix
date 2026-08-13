# Phone capture

Ambient audio from the operator's phone (Redmi Note 11, Android 13/API 33,
unrooted, bootloader locked) into the lake at
`/realm/data/captures/phone/ambient`.

## Why an app

The previous arrangement was a Termux script under runit. It failed twice, in
two different ways, and both failures trace to the same root cause: Termux
cannot declare a microphone foreground service.

- **Truncation.** Android cuts microphone access for a process that is not
  foreground-important. Chunks kept landing every five minutes while
  containing seconds of audio — mean 148s against an expected 300s, with 14 of
  60 chunks under 10 seconds.
- **No reboot survival.** Ten minutes after a reboot there were zero Termux
  processes and zero chunks. What survived was every piece of policy state
  that had been set by hand (Doze whitelist, MIUI no-restrict list, the
  package-scope appop); what did not survive was the UID-scope appop, and the
  boot chain failed silently with no headless way to restart it.

`foregroundServiceType="microphone"` with a persistent notification is the only
supported way to hold the microphone with the screen off on modern Android,
and it can only be declared in an app's manifest. That single capability is
what makes this an app rather than a script.

A second, unplanned benefit: `am start -n dev.sinnix.phone/.MainActivity`
works from the desktop, so capture has a headless recovery path. The same
command against Termux returns "Activity class does not exist" whenever the
screen is locked.

## Where it lives

| Piece | Path |
| --- | --- |
| App source | `pkgs/sinnix-phone-app/app/` |
| Build + install packaging | `pkgs/sinnix-phone-app/pkg.nix` |
| Desktop control surface | `scripts/sinnix-phone` (`app-*` subcommands) |
| Scheduled drain | `modules/services/phone-drain.nix` |

## Build toolchain

No Gradle. Gradle resolves dependencies from the network at build time, which
a Nix derivation cannot do without vendoring a dependency lock, and it buys
nothing here because the app has no third-party dependencies at all — only
platform APIs, with the UI built in code so there are no layout resources to
compile. The derivation therefore calls the four tools underneath Gradle
directly: `aapt2 link` for the manifest, `javac`, `d8`, `zipalign`.

The Android SDK is unfree and license-gated, so `pkg.nix` re-imports nixpkgs
via `pkgs.path` with `android_sdk.accept_license = true`, keeping the same
nixpkgs revision as the rest of the flake.

The APK is emitted **unsigned**. `sinnix-phone-app-install` signs it against a
keystore at `~/.local/share/sinnix-phone-app/keystore.jks`, created on first
use and persisted (`modules/services/phone-drain.nix`). A key regenerated on
every source change would make each `adb install -r` fail with a signature
mismatch and force an uninstall, which on Android also discards the app's
runtime grants.

## Operating it

```
sinnix-phone app-install    # build, sign, sideload, grant, start
sinnix-phone app-status     # is capture alive AND producing?
sinnix-phone app-start      # relaunch after the app was stopped
sinnix-phone app-grants     # re-assert shell-uid grants
```

`app-install` needs adb over USB or the tailnet, **and the phone must be
unlocked**. MIUI routes every adb install through its own
`com.miui.permcenter.install.AdbInstallActivity` confirmation dialog, which
cannot be shown over the keyguard; the install is then auto-cancelled with
`INSTALL_FAILED_USER_RESTRICTED`. There is no desktop-side workaround —
`pm install -i com.android.vending` and plain `pm install` are refused
identically. Upgrades and fresh installs are both affected.

`app-install` is safe to re-run, and on success it retires the Termux runit
`ambient` service (a `down` file, so the retirement survives reboots) so the
two recorders can never contend for the microphone.

Grants applied by `app-grants`: `RECORD_AUDIO` and `POST_NOTIFICATIONS` as
runtime permissions, `MANAGE_EXTERNAL_STORAGE` as an appop at **both** package
and uid scope, and the Doze whitelist. The two appop scopes are set separately
because only one of them reverting is exactly what broke capture before.

`RECORD_AUDIO` is deliberately *not* forced to appop `allow`. The default
`MODE_FOREGROUND` should already be satisfied while the microphone-typed
foreground service is up; overriding it would mask a service regression rather
than fix one.

On the appop scope split that broke the Termux arrangement: `appops get
<pkg> RECORD_AUDIO` reports a **uid mode** and a **package mode** separately,
only the package mode was ever set, and the uid mode reverted to `foreground`
across a reboot. For this app that reversion should be harmless rather than
fatal, because `foreground` is satisfied by a microphone-typed foreground
service — that is the entire difference from Termux, which could not declare
one. That claim is **not yet proven in isolation**: during the screen-off
measurement the package mode had been manually set to `allow` beforehand, so
the run does not separate "the foreground service satisfied it" from "the
appop was open anyway". Uninstalling clears per-package appop state, so the
next install is a clean test of it — `app-grants` will leave `RECORD_AUDIO` at
its default deliberately.

## Acceptance criteria

Three cases, and they are genuinely different. The operator's requirement is
that capture does not stop when the phone is merely used or restarted:

1. **Screen off / app backgrounded.** Solved by
   `foregroundServiceType="microphone"`. Verified: three consecutive chunks at
   299.968s against a 300s target, mean volume -37.1 dB, while
   `mWakefulness=Dozing` and the process held the platform's `M` (microphone)
   capability.
2. **Phone actively in use** — another app foreground, the operator typing,
   audio playing. *"Capture not working when telephone is handled is not
   acceptable."* **Not yet verified.** This is not implied by case 1; see the
   arbitration limit below.
3. **Reboot.** Not yet verified; resumes at first unlock (see Known limits).

`sinnix-phone app-soak [seconds]` is the test for 1 and 2 together. It samples
screen state, foreground app, heartbeat age, and mute state across a window,
then measures every chunk closed inside it. It reports the foreground app per
sample so "the phone was in use" is evidence rather than a claim, and refuses
to read a stale `status.json` as liveness.

### The arbitration limit

`foregroundServiceType="microphone"` buys the right to keep the microphone
while backgrounded or with the screen off. It does **not** win Android's
concurrent-capture arbitration. When a foreground app opens the microphone,
the platform can hand it the input and feed this service **digital silence** —
no error, no exception, and the encoder keeps producing frames at the same
bitrate. Chunk duration and file size stay perfect while the audio is nothing.

That is why the service tracks `MediaRecorder.getMaxAmplitude()` per
heartbeat. A live microphone in a silent room still reports its own noise
floor, so a sustained run of *exact* zeroes means muted rather than quiet.
Four consecutive zero samples (80s) is treated as a failure and cycles the
recorder, and `muted` plus `last_amplitude` are published in `status.json`.

Detection is not prevention. If Android decides a foreground app wins, cycling
the recorder may not take the microphone back. Case 2 is therefore an
empirical question about this device's policy, which is exactly why it has to
be measured rather than reasoned about. Phone calls are a known hard stop:
Android has blocked third-party call audio capture since Android 10, and no
manifest declaration changes that.

## Liveness

The app writes `/sdcard/sinnix-ambient/status.json` every 20 seconds, and
`sinnix-phone app-status` reads it over whichever adb transport is up — USB
included. That matters because adbd's TCP mode does not survive a reboot and
the phone's tailnet is often down at the same moment, so liveness must not
depend on Termux, sshd, or the tailnet: those are precisely the layers that
kept failing.

Three readings, because none of them alone is sufficient:

- `status.json` contents say what the app believes about itself.
- The file's own age says whether the app is still there to believe anything.
  Past ~2 minutes the process is gone, not idle.
- `ffprobe` on the newest closed chunk says whether the bytes are audio. A
  recorder muted by the platform still produces a file every five minutes,
  which is how the truncation bug stayed hidden.

The app applies the same reasoning to itself: if the chunk file it is writing
stops growing for 90 seconds, it treats that as a failure and cycles the
recorder rather than continuing to believe it is recording.

## Chunk convention

Files are `/sdcard/sinnix-ambient/ambient-<UTC ISO basic>.m4a`, ~300s, mono
16 kHz AAC at 48 kbps (~1.8 MB/chunk) — 16 kHz because every downstream
consumer is speech recognition.

The file currently being written is named `*.m4a.part` and renamed only after
the muxer closes it. The drain rsyncs with `--remove-source-files`, which
would otherwise delete the open file and lose its trailing `moov` atom; the
drain excludes `*.part` and `status.json`.

A `.part` file found at service startup belongs to a recorder that died
without closing its muxer. The service renames those to `*.m4a.orphan`, which
the drain *does* collect — otherwise a skipped-forever file would accumulate
on the phone, invisible. They are renamed rather than deleted: an MP4 without
its `moov` atom is not playable but the samples are still there, and
discarding captured audio is not the device's call.

## Known limits

- **Reboot resumes at first unlock, not at power-on.** The device uses
  file-based encryption with a screen lock, so `BOOT_COMPLETED` is delivered
  after the first unlock and `/sdcard` is not mounted before it. No app has to
  be opened and nothing has to be tapped, but a phone left locked after a
  reboot is not capturing. Making this truly unattended needs Direct Boot
  handling: a `directBootAware` service buffering into device-protected
  storage and migrating on unlock.
- **MIUI background autostart** has no adb assertion path (`sinnix-r0k3`).
  The watchdog alarm and `START_STICKY` cover process death; they do not cover
  MIUI refusing to deliver the boot broadcast at all.
- Sensors, location, and battery/thermal are not captured yet. The app is the
  intended owner of those (`sinnix-uyvt.4`).
- Phone calls stop capture. Android has blocked third-party capture of call
  audio since Android 10; this is a platform decision, not a configuration
  gap.

## Service boundary

`AmbientService` is drivable without the UI, which keeps it usable underneath
a richer interface later (a sibling lane is designing one). The contract is:
`ACTION_START` / `ACTION_STOP` intents, a single persisted intent bit in
`Prefs` that boot and watchdog restarts consult, and `status.json` as the
read model. `MainActivity` is only a client of that contract — it starts the
service, toggles the preference, and renders `status.json`. Nothing in the
capture path calls back into the activity, so replacing or extending the UI
does not touch the recorder.
