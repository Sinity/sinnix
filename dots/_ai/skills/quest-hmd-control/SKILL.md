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

## Evidence to collect

For each action, capture the foreground activity, the relevant host service or
protocol state, and the headset package state. For media, test a byte-range
request over the same LAN or ADB-reversed URL that the player will use.

## Boundaries

Do not expose pairing tokens, device identifiers, or private media paths in
tracked text or chat. Do not bypass third-party account, privacy, or terms
screens. Do not use fixed-coordinate automation in immersive apps; document
the missing control surface and use native protocol evidence instead.
