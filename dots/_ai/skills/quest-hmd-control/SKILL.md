---
name: quest-hmd-control
description: Control and verify a Meta Quest HMD through ADB, app intents, media forwarding, and immersive-session evidence. Use for Quest setup, pairing, streaming, capture, or headset UI beyond ordinary Android automation.
---

# Quest HMD control

Use this alongside `android-device-control` and `sinnix` when a Quest is in
scope. Work against the selected serial only, and prove it is the intended
headset before mutating state.

## Control ladder

1. Prefer package facts and explicit intents: check installation and resolved
   activities, then launch known apps by package/activity or supported deep
   link.
2. Use ADB reverse for a wired IP path, application-native protocols for
   pairing, and host service APIs for their owned state. Verify the resulting
   service, socket, or client record instead of treating an intent exit code as
   success.
3. Use `uiautomator` only for normal Android panels. A black screenshot or an
   empty accessibility tree while the VR shell is foreground is evidence of an
   immersive compositor, not a reason to guess coordinates or repeat taps.
4. When an immersive confirmation still requires controllers, send a concise,
   one-time local headset notification when authorized, watch the host-side
   pairing/session event, and resume automatically once it appears.

## PC video commands

Use the installed `sinnix quest video` command. `open` records one selected
file in private runtime state and serves it from the foreground on host
loopback through an ADB reverse tunnel. `--detach` transfers that ownership to
the fixed user service. Both modes work through either the verified USB or
authenticated network ADB transport without opening a media port on the LAN:

```sh
sinnix quest video open /path/movie.mp4
sinnix quest video open --clipboard
sinnix quest video choose /realm/library/videos --stereo off
sinnix quest video status
sinnix quest video seek +10
sinnix quest video speed 1.25
sinnix quest video pause
sinnix quest video resume
sinnix quest video stop
```

Use `--projection dome` for 180-degree content, `sphere` for 360-degree
content, and `--stereo off` for mono. Specify `--codec` and `--height` to
match the file. `--cold` restarts DeoVR and may trigger the Quest app lock.
`browse URL` opens a player-native HTTP(S) library endpoint.

Remote commands require DeoVR's **Enable remote control** setting and an
active video. Pause/resume are capability probes: they fail unless the
requested state is observed. Do not substitute Android media keys: another
app such as KDE Connect can own the active Android media session.

`Super+P` opens the clipboard's local path or `file:` URI in a visible Kitty.
The media play, next, and previous keys control an active Quest session; when
none is active they retain their ordinary `playerctl` behavior. These controls
require live headset verification because DeoVR must first have remote control
enabled. Protocol source: [DeoVR documentation](https://deovr.com/documentation).

## Session verification

For each action, capture the foreground activity, the relevant host service or
protocol state, and the headset package state. For media, test a byte-range
request over the same LAN or ADB-reversed URL that the player will use.

## Boundaries

Do not expose pairing tokens, device identifiers, or private media paths in
tracked text or chat. Do not bypass third-party account, privacy, or terms
screens. Do not use fixed-coordinate automation in immersive apps; document
the missing control surface and use native protocol evidence instead.
