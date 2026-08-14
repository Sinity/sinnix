# Sinnix Capture — app design

The recorder's contract lives in `docs/phone-capture.md`; this is the design of
the thing around it. Written against the iteration-two Claude Design pass and
the corrections that followed it, so it records decisions rather than options.

## What the app is

A capture, measurement and action surface for the phone, and a native way to
reach the estate on prime. It is not a dashboard for the recorder — that is one
screen inside it.

The build is framework-only: no Gradle, no Kotlin, no AndroidX, no third-party
libraries, and no XML resource tree (`pkgs/sinnix-phone-app/pkg.nix` calls
aapt2, javac, d8 and zipalign directly). Views are constructed in code and
anything graphical is a `Canvas` subclass.

**Why no Gradle, and what it does not mean.** Nix builds run without network
while Gradle resolves dependencies over the network, so a Gradle build inside a
derivation needs its artifacts vendored first. nixpkgs supports exactly that,
and not as a bespoke effort: `fetchmavenartifact` pins a single artifact by
group/artifact/version and hash, and the Gradle setup hook records a whole
build's fetches through `mitm-cache` into a derivation, with `update-deps.nix`
to regenerate it. This app simply had nothing to resolve, so the derivation
calls the four tools Gradle would have called anyway.

So the ladder is about how much machinery a dependency is worth, not about
what is possible:

- **A plain JAR** is nearly free — fetch it, put it on the `javac` classpath.
- **An AAR carrying resources** (which is most of AndroidX) needs resource
  merging through `aapt2`, which this build deliberately does not do. That is
  the first real cost, and it grows with the transitive closure.
- **A full Gradle project** is the nixpkgs pattern above: supported, but a
  standing mechanism to maintain.

Nothing below is blocked by the build. Where a limit is stated, it should be
read as "not worth that machinery yet", and revisited when something is.

Two consequences that decide features rather than styling:

- **No model runs on the phone today.** The on-device toolkits (MediaPipe,
  ML Kit, TFLite) are AARs with native libraries and, for ML Kit, a Play
  Services dependency — squarely in the "real machinery" tier above. Nothing
  makes them impossible; none has yet been worth that.

  The working division of labour makes that easy to live with: **the phone
  owns stimulus timing and raw capture, prime owns scoring.** Prime has the
  CPU, the models, and the operator's whole history to compare a number
  against, so almost every instrument is better off scored there regardless of
  what the APK could contain.

  The eye and face instruments — pupillometry, saccades, blink, face-video
  pulse — are dropped on their own merits rather than on the build: each needs
  continuous video shipped to prime, a large stream to move and store for a
  measurement that says comparatively little. Worth revisiting if the value
  ever justifies the pipe.
- **No app widget.** `AppWidgetProvider` requires `RemoteViews`, which requires
  an XML resource tree. The quick-settings tile and the notification cover the
  same ground and need no resources.

## No network code

The app opens no sockets. Every arrow between phone and prime is a file, and
`sinnix-phone` is the only transport. This is not minimalism: adbd's TCP mode
does not survive a reboot and the tailnet is frequently down at exactly the
moment something needs checking, so a design that reached the network would be
a design that stops working when it matters.

The consequence is stated in the UI rather than hidden: an action prime must
execute reads `queued · next drain`, never `sent`.

## Trust grades, and where they stop

Three grades — **evidenced / unverified / broken** — with one rule: no green
without named evidence, and anything the app cannot verify renders as
`unverified`, never as OK.

They apply on **capture detail** and **grants**, and nowhere else. That
boundary is deliberate and was got wrong once. The failures that motivate the
vocabulary are real and ongoing on those two screens: MIUI revokes grants with
no event, a foreground app can win microphone arbitration and feed the recorder
silence mid-use, and 29 of 111 chunks in the existing archive turned out
well-formed and empty. Distinguishing "measured OK" from "assumed OK" there is
accurate rendering.

Applying the same chrome to home, instruments, Talk or the estate remote would
dress the whole app in reliability-engineering vocabulary — making dev-time
incident history the centre of a tool whose actual centre is capture,
measurement and action. The one echo allowed elsewhere is latency honesty on
action labels (`queued · next drain`).

## What was cut, and why

**The device-profile screen and its per-rate verdict table.** It existed to
render a per-rate `ok / silent / unprobed` ladder, on the premise that a sample
rate could be accepted by the API and return digital silence. That premise was
false: the one silent chunk was recorded while a second recorder held the
microphone during a reinstall, and 48 kHz records normally (mean -37.4 dB over
a full segment). A screen whose whole subject does not exist is not worth
building, and a rate ladder driven by that theory was built and removed in one
commit.

What survives from it is the **apparatus epoch**, which instruments genuinely
need: `Build.FINGERPRINT` plus the measured touch-latency offset, as its own
small record, decoupled from sample rates entirely. A result is only comparable
to results from the same epoch, and every result prints which.

The generalisable lesson survives too, and it is why `ambient-audit` exists on
the desktop side: **known-good means decoded.** A successful `prepare()`, a
plausible file size, an exact duration and a valid container are all consistent
with total silence.

## Files, which are the whole data layer

```
/sdcard/sinnix-ambient/          the recorder's lane, service-owned
  ambient-<UTC>.m4a[.part]       chunks
  status.json                    20s heartbeat
/sdcard/sinnix-phone/            the app's estate
  events/events-YYYYMMDD.jsonl   append-only, drained whole
  epoch.json                     fingerprint + touch offset
  inbox/                         prime -> phone, written by the drain
  outbox/                        phone -> prime, consumed by the drain
```

`events/*.jsonl` is the app's own record and the source for anything historical
the UI shows — the ribbon, holes, grant transitions, instrument runs. It is
append-only because a reducer can always re-read it, and because a file the app
rewrites is a file the app can corrupt.

Holes are **first-class objects** with a start, an end, a cause and what
recovered them, derived at chunk close. A gap the app can explain is worth more
than a gap someone has to reconstruct later, and `sinnix-hcjq` was a hole with
no explanation.

## Screens

**Home.** One scroll. A 7-day × 24-hour continuity ribbon (the capture-trust
surface, tapping into the diagnosable version); at most one ask card, never a
list, with an empty state that occupies the same space rather than collapsing;
three thumb-height actions. Phone continuity and lake continuity are separate
rows and are never merged — the drain tolerating a 24-hour gap is deliberate,
because a phone off wifi is not a fault.

**Capture detail.** The diagnosable view: status fields, per-chunk grade with
its evidence line, holes, the lake's backlog, and stop. The open chunk is never
green — it renders as in-progress with its live amplitude. A silent closed chunk
is kept, flagged and drained: evidence of failure is data, and deleting
captured bytes is not the device's call.

**Grants.** Evidence beats API reads wherever a probe is possible — all-files
access is graded by actually creating and deleting a file in the handoff
directory, because the API answering `true` while MIUI blocks the path is
exactly this platform's habit. MIUI autostart is structurally unverifiable and
says so; it carries an attestation timestamp and a boot-inference row beneath
it, since a reboot is the only real test and the app treats each boot as one.

**Instruments** are never a catalogue. The container is a *check*: two to four
instruments, under three minutes, assembled by policy. Build order starts with
PVT, which is validated, robust to apparatus, directly sensitive to the sleep
question, and carries the touch-latency calibration everything else depends on.

**Off-screen** is where the app mostly lives: a forced ongoing notification
carrying uptime and backlog, separate channels so classes can be silenced
independently, and a quick-settings tile. The tile deliberately does **not**
toggle capture — a control that can stop a 41-hour recording with one mis-swipe
is a hazard, not a convenience.

## Deferred, with the blocker named

The steering surfaces — morning ritual, resolve, ready queue — need a
prime → phone push channel that no module provides today: `phone-drain` is
pull-only and never writes to the device. That is `sinnix-5h8e`, and it is the
actual blocker rather than a sequencing preference.

## Build order

1. Foundation — events log, epoch record, grade vocabulary and the Canvas views.
2. Capture trust end to end — home, capture detail, grants, notification
   channels, tile. Ships alone and replaces the diagnostic activity.
3. Instrument runner and PVT, epoch-aware.
4. EMA and breath counting.
5. Hold-to-talk.
6. Staircases, then the hold-still pattern (PPG, tremor, sway).
7. Steering, after the push channel exists.
