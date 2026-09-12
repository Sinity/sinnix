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

The adjacent [player.py](player.py) runs directly from dots with Python 3;
it uses `sinnix quest adb` for verified device selection. No system rebuild
is required. Examples from this skill directory:

```sh
python3 player.py open /path/movie.mp4 --stereo sbs --projection flat
python3 player.py status
python3 player.py seek +10
python3 player.py speed 1.25
python3 player.py pause
python3 player.py resume
```

`open` stays foreground and serves only the chosen file on loopback with an
ADB reverse. Stop it with Ctrl-C. Use `--projection dome` for 180-degree
content, `sphere` for 360-degree content, and `--stereo off` for mono.
Specify `--codec` and `--height` to match the file. `--cold` restarts DeoVR
and may trigger the Quest app lock again.

Remote commands require DeoVR's **Enable remote control** setting and an
active video. Pause/resume are capability probes: they fail unless the
requested state is observed. Do not substitute Android media keys: another
app such as KDE Connect can own the active Android media session.

Any command can be bound to a PC hotkey. Run `open` in a terminal so its
server lifetime and errors remain visible. These helpers have transport
tests, but live playback and remote mutation must still be verified on the
headset. Protocol source: [DeoVR documentation](https://deovr.com/documentation).

## Session verification

For each action, capture the foreground activity, the relevant host service or
protocol state, and the headset package state. For media, test a byte-range
request over the same LAN or ADB-reversed URL that the player will use.

## Boundaries

Do not expose pairing tokens, device identifiers, or private media paths in
tracked text or chat. Do not bypass third-party account, privacy, or terms
screens. Do not use fixed-coordinate automation in immersive apps; document
the missing control surface and use native protocol evidence instead.
