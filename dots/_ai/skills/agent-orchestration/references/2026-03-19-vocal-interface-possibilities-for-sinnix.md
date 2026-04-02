# Vocal Interface Possibilities for Sinnix

## Executive summary

A voice surface can materially improve **operator ergonomics** for a local-first coding-agent environment on NixOS/Wayland *if* it is treated as a **constrained command-and-control channel** (plus optional spoken notifications), not as a “talk to your computer all day” gimmick. The highest ROI is in “meta-operations” like **switching sessions, asking status, interrupting/aborting, and approving/denying**—especially when many sessions exist and your hands/eyes are busy. The lowest ROI is freeform dictation of code-identifiers and shell commands, because transcription errors are costly and error recovery is slow unless you invest in a full “voice coding” stack. fileciteturn45file0L1-L1 citeturn3search9turn3search12

Sinnix already has unusually strong building blocks for a serious voice surface on a Wayland desktop:

- A Hyprland-based workflow with a rich keybinding layer (including audio/mic toggles) suitable for “hotkey-gated capture.” fileciteturn45file0L1-L1
- PipeWire tooling already in active use (`wpctl`, `pw-dump`) and a dedicated mic-toggle script, which supports a privacy-first posture (“mic muted by default; only unmute in capture windows”). fileciteturn48file0L1-L1 citeturn1search2
- fnott notifications + Waybar, making it straightforward to provide both **visual** and **auditory** feedback and avoid “ghost commands.” fileciteturn43file0L1-L1 fileciteturn50file0L1-L1

For a first implementation slice, the most realistic design is:

- **Hotkey → one-shot speech capture → local STT → strict command grammar → confirm → execute Sinnix session command**.
- Optional short **earcons** (beeps) and/or short TTS acknowledgements via Speech Dispatcher priority levels (so voice output is rate-limited and non-intrusive). citeturn4search17turn5search1

Local-first STT/TTS is feasible with nixpkgs today: `whisper-cpp` (local Whisper inference) and `piper-tts` (local neural TTS) are packaged. citeturn4search0turn3search13 For wake-word / always-listening, there’s direct NixOS support for openWakeWord via the Wyoming ecosystem, but it should be a later phase due to accidental activation and privacy/attention costs. citeturn5search18turn5search15turn2search3

A critical reliability point: modern STT systems can insert text that was not spoken (“hallucination” / confabulation) in some conditions, so voice actions must be treated as **untrusted input**, with confirmations for destructive operations and strong visible feedback. citeturn0news49

## Candidate voice use cases ranked by value

This section assumes the “phase 1” architecture direction where Sinnix sessions are durable and enumerable. Voice is evaluated across your requested categories as **clearly useful / situationally useful / mostly a bad fit**.

### Highest value: command-and-control for session operations

**Voice: clearly useful** when the spoken utterance can map to a small, well-defined action set and the system can show immediate feedback.

- **Session switching / attach / detach (multi-session navigation)**
  Why it works: it’s a “menu operation,” not creative text entry. It benefits from hands-busy scenarios (holding coffee, standing desk movement, wiring hardware). A voice command like “attach auth refactor” can be safely routed to “open viewport + attach session.” fileciteturn45file0L1-L1
  UX prerequisite: sessions need **short speakable aliases** (discussed later).

- **Interrupt / stop / steer commands**
  Example: “stop session auth refactor,” “pause all agents,” “abort current run.”
  This is where voice can beat keyboard when you’re focused elsewhere on-screen or across monitors. Because it’s destructive, it must require confirmation for anything beyond “pause/interrupt.” citeturn4search17turn0news49

- **Status queries and listing**
  Example: “what’s running,” “status auth refactor,” “which sessions need approval.”
  Voice is especially effective if it returns a *short* answer plus an on-screen notification (fnott) containing the full details so nothing is lost. fileciteturn43file0L1-L1

- **Approval handling**
  Example: “approve last request,” “deny, and explain: no network.”
  Even if the underlying agent tool has its own approval UI, a Sinnix layer can treat “approve/deny” as a meta-operation and route it through the existing session control plane. (This remains a future hook for sinex-style exocortex coordination; for now, keep it local and explicit.)

### Medium value: voice as a prompt input channel

**Voice: situationally useful** when used to speak natural language prompts, summaries, or high-level instructions—*not* precise code.

- **Direct dictation into an agent** (freeform prompting)
  Useful for “talking through” intent: “Find why integration tests are flaky; propose hypotheses; start with logs.”
  Risk factors: technical tokens (paths, flags, identifiers) are error-prone; long prompts are hard to proofread in audio form; and certain STT systems can confabulate. citeturn0news49
  Practical guidance: keep spoken prompts short; prefer “plan-level” directives, and rely on the agent to ask clarifying questions rather than dictating exact commands.

- **Summary requests**
  Example: “summarize what session auth refactor changed.”
  This is a good fit if the response is shown in a TUI/notification and optionally spoken back in a short form. For long responses, spoken-only is a poor medium.

### Medium value: spoken readback and passive notifications

**Voice: situationally useful** if designed carefully to avoid overload.

- **Passive spoken notifications** (completion, blocked on approval, failure)
  The sweet spot is: *earcon* for most events, and TTS only for high-severity or explicit “read it” requests. Speech Dispatcher provides message priority classes (including “notification” and “progress”), which can help implement severity-aware audio. citeturn4search17turn5search1

- **Spoken readback of results**
  Good for one-liners: “tests passed,” “three sessions need approval,” “session X is waiting.”
  Bad for multi-paragraph diffs or complex diagnostics; those should be visual-first.

### Low value: “voice coding” and always-listening modes

**Voice: mostly a bad fit** for Sinnix *unless* you decide you’re committing to a Talon-style voice coding workflow (which is a separate product-level choice).

- **Dictating shell commands, file paths, identifiers, punctuation-heavy text**
  Unless you have a specialized system with modes and strong correction UX, transcription mistakes can cause dangerous or simply frustrating outcomes. Talon’s community practice explicitly distinguishes command mode and dictation mode, and uses “sleep mode” to avoid accidental actions—this is a major investment category, not a “light integration.” citeturn3search9turn3search12

- **Mobile-around-the-room interaction** (far-field, wake word, always listening)
  This tends to require wake word detection, robust device routing, and careful privacy posture. It can be done locally (openWakeWord, Wyoming), but it introduces high accidental activation risk and is usually hard to make “pleasant day-to-day” on a workstation. citeturn2search3turn5search18turn5search15

## Interaction model comparison

The key decision is not “voice or not,” but *which speech capture model* best fits a terminal-native operator who values control and low distraction.

### Interaction models table

| interaction model | ergonomics | accidental activation risk | latency tolerance | error recovery UX | privacy posture | fit for coding-agent ops |
|---|---|---:|---|---|---|---|
| Push-to-talk (hold) | excellent when hands are on keyboard; clear mental model | very low | tolerant of moderate STT latency | good (release-to-cancel is intuitive) | strong (non-listening by default) | strong for commands; weak for long dictation |
| Hotkey-gated “one-shot capture” (press once, speak, VAD ends) | excellent for workstation; simplest to implement on Wayland | low | tolerant; can show “listening” indicator | good if it shows recognized text + confirm | strong if mic muted by default | **best first slice** on Sinnix |
| Wake word + follow-up speech | convenient hands-free | medium–high (false wakes) | must be low-latency to feel good | harder (need “cancel” voice + UI) | weaker (always listening) | potentially useful later, but risky |
| Always-listening local assistant | hands-free | high | must be very low | hard | weakest | poor fit for a workstation |
| Hybrid (voice commands only; no freeform) | high | low | tolerant | excellent if grammar is small | strong | **ideal** for multi-session management |
| “Voice command palette” (speak → shows options in tofi/overlay → confirm) | high; combines voice speed with visual disambiguation | low | tolerant | excellent (visual selection) | strong | extremely good for multi-session selection |
| Spoken summaries / TTS only (no STT) | low operator control benefit | none | not relevant | not relevant | strong | good complement for notifications, not primary control |
| Duplex conversational mode (voice in/out loop) | charming but attention-heavy | medium | must be low | hard | weaker, more capture | generally not a good fit for session management |

This table reflects a strong bias toward **hotkey-gated** capture and **command-only grammar** for your environment, because it allows strict safety UX, avoids wake-word complexity, and leverages your existing Hyprland keybinding surface. fileciteturn45file0L1-L1

### Why “hotkey-gated one-shot capture” is the best first slice for Sinnix

- Wayland compositors like Hyprland already act as the policy layer for global hotkeys (your current setup uses many `exec` bindings). fileciteturn45file0L1-L1
- You already have a PipeWire-native mic toggle (`wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle`) and UI surfaces (Waybar, fnott) that can reflect “listening now” state. fileciteturn48file0L1-L1 fileciteturn50file0L1-L1
- It reduces privacy concerns relative to always-on audio capture. PipeWire’s NixOS documentation emphasizes explicit capture/permission models (especially relevant for portal-captured media), and your script-based audio management aligns with this mindset. citeturn1search2

## Technical stack options

The core technical problem is: **capture audio reliably on PipeWire → detect speech boundaries (VAD) → transcribe (STT) → parse into safe commands → execute → provide feedback (visual+auditory)**.

### Concrete audio pipeline fit on your workstation

- Capture and playback can be done using PipeWire tools; `pw-record`/`pw-cat` support recording/playback and can use STDIN/STDOUT, which is convenient for a CLI-first design. citeturn2search0
- Your existing `audio` script uses `wpctl` and `pw-dump` already, meaning the system expects PipeWire + WirePlumber and has the primitives to toggle mic state and read device status. fileciteturn48file0L1-L1

### STT / TTS / VAD / wake word comparison table

The table below focuses on options that are (a) local-first capable, (b) plausibly packageable/operable on NixOS, and (c) realistically maintainable. Version/date context is as of **2026-03-19** based on Nix package metadata and upstream docs.

| component | option | local/offline | practical latency profile | technical vocabulary handling | NixOS fit | integration complexity | notes |
|---|---|---|---|---|---|---|---|
| STT | Whisper via `whisper-cpp` (nixpkgs `whisper-cpp` v1.8.2) | yes | good for short utterances; non-streaming UX typically means chunking | generally robust; Whisper is trained on large-scale multilingual data and is described as better with accents/noise/technical language than many prior systems (but not perfect) citeturn0search3turn0search13 | strong (packaged) citeturn4search0 | moderate | strong default STT for short commands + “dictate a prompt” use; still must treat output as untrusted citeturn0news49 |
| STT | OpenAI Whisper (python package) | yes | depends on runtime + model size | similar to above | strong (packaged as `openai-whisper`) citeturn4search5 | moderate-high | heavier Python stack; still viable if you already accept Python deps |
| STT | Vosk (offline toolkit) | yes | explicitly designed for streaming/low-latency; supports small models | supports vocabulary reconfiguration / adaptation; good for constrained grammars citeturn1search0turn1search7 | medium (packaging varies; Python `vosk` is trivial to install; also has docs) citeturn0search4turn1search0 | moderate | ideal for command grammars and fast partial results; may be less robust than Whisper for unconstrained dictation (inference) |
| STT | OpenAI Audio API transcription (`gpt-4o-mini-transcribe`, `gpt-4o-transcribe`, diarize) | no (cloud) | high quality; network-dependent | strong; supports diarization variants citeturn3search8 | high (API client) | medium | best “hybrid fallback” when local STT fails; not local-first |
| VAD | WebRTC VAD (`webrtcvad`) | yes | very low latency; frame-based | doesn’t do transcription; just speech/no-speech | medium (Python dependency) citeturn2search2 | low | accepts 10/20/30ms frames, limited sample rates; has aggressiveness levels 0–3 citeturn2search2 |
| VAD | Energy threshold / simple RMS | yes | very low | brittle in noise | high | very low | good only as fallback; tends to be annoying in real rooms (inference) |
| Wake word | openWakeWord | yes | designed for streaming; processes 80ms frames; outputs confidence score 0–1 citeturn2search3 | n/a (keyword spotting) | medium-high (python; also packaged via Wyoming ecosystem) citeturn2search3turn5search5 | medium | reasonable for later; introduces always-listening implications |
| Wake word | NixOS `services.wyoming.openwakeword` | yes | depends on server mode; threshold configurable | n/a | strong (has NixOS module + options like threshold, package) citeturn5search18turn5search15turn5search13 | medium-high | best if you want standardized wake-word infra; but it’s “heavier” than hotkey-gated capture |
| TTS | Piper local (`piper-tts` in nixpkgs v1.3.0; PyPI shows continued releases with 1.4.1 in Feb 2026) | yes | good for local spoken output; supports local synthesis pipeline | good intelligibility; quality depends on voice model | strong (packaged) citeturn3search13turn1search3 | medium | good default for short spoken summaries |
| TTS | Speech Dispatcher + eSpeak NG | yes | very low latency, especially for short phrases | robotic but clear; has spelling and punctuation modes via spd-say citeturn4search17turn5search0turn5search1 | strong (packaged) citeturn5search1turn5search0 | low-medium | best “control plane voice”: quick, low resource, supports priority classes citeturn4search17 |
| TTS bridge | `pied` (Piper voice manager for Speech Dispatcher) | yes | depends on Piper | n/a | strong (packaged) citeturn5search11 | medium | promising: unified spd-say UX with high-quality Piper voices |
| TTS | OpenAI TTS (`gpt-4o-mini-tts` etc) | no (cloud) | high quality; streaming possible; network-dependent citeturn3search1 | good | high | medium | best hybrid fallback or for higher-quality spoken summaries; not local-first |
| Duplex voice | OpenAI Realtime API | no (cloud) | designed for low-latency speech-to-speech; persistent connection; supports interruption handling citeturn3search0turn3search2 | good | medium | high | powerful, but violates strict local-first unless optional fallback |

### Practical stack recommendation for Sinnix

For a first slice on your workstation:

- **PipeWire capture**: `pw-record` feeding a local processor. citeturn2search0
- **VAD**: WebRTC VAD to cut latency and reduce accidental capture. citeturn2search2
- **STT**: `whisper-cpp` locally (fast path), with an optional Vosk “command grammar engine” later for ultra-fast and vocabulary-constrained recognition. citeturn4search0turn1search0turn1search7
- **Feedback**: fnott visual notifications + optional TTS via `spd-say` with “notification/progress” priorities. fileciteturn43file0L1-L1 citeturn4search17turn5search1

## Multi-session voice UX recommendations

Voice becomes hard when many sessions exist; the design must avoid ambiguity and prevent destructive errors.

### Session naming that is speakable, disambiguatable, and stable

Use **two names** per session:

- A **human title** (“auth refactor,” “flake eval cleanup”)
- A **short alias** optimized for speech: e.g., `auth-one`, `auth-two`, or NATO-ish + digits (“alpha four”).

This mirrors the core voice UX lesson from accessibility/voice tooling: spoken references must be short and phonetic. Talon’s ecosystem relies heavily on explicit modes and commands defined in `.talon` files, including global commands and hotkeys; it succeeds because commands are intentionally short and consistent. citeturn3search5turn3search9

### Targeting rules: “active session” vs explicit session

Adopt a simple hierarchy:

1. If the utterance includes a session alias → target that session.
2. Else → target the “current active session” (focused terminal/viewport).
3. If ambiguous → present a *visual disambiguation list*.

This is where a “voice command palette” shines: after STT, show a tofi list of candidates and let the operator select with arrow keys/enter. (Sinnix already uses tofi as launcher.) fileciteturn43file0L1-L1

### Disambiguation UX

When multiple sessions match, do **not** ask a long spoken question. Instead:

- Show fnott notification: “Which session? (1) auth-refactor (2) auth-migration …”
- Optionally speak: “Two matches. Check the popup.”
- Accept a follow-up voice “one” / “two” if you want, but keyboard selection is usually faster.

### Safety model for destructive commands

Because voice transcription can be wrong—and can even produce words that weren’t spoken in some cases—you need a “two-phase commit” for destructive actions:

- Phase 1: recognize intent → display it (big, obvious) → speak “confirm?”
- Phase 2: accept “confirm” (or a second hotkey press) within a short timeout.

This is not paranoia: there are well-documented cases of Whisper-based systems producing fabricated text, which is unacceptable as a direct execution channel. citeturn0news49

Concrete guidance:

- **No confirmation needed**: list, status, attach, observe, summarize.
- **Confirmation required**: stop/terminate, approve/deny, “run shell command,” “kill all.”
- **Confirmation + visual**: anything that changes files or agent permissions.

### “Observe but don’t control” voice model

If your session substrate supports observe-only (as discussed in phase 1), voice should expose it distinctly:

- “observe auth-one” opens a read-only viewport.
- “attach auth-one” opens an interactive viewport.

Even without implementing full multi-client semantics on day 1, this helps reduce “oops I stole control” incidents.

### Spoken summaries from detached sessions

Use two tiers:

1. **Short spoken status** (one sentence): “auth-one is idle; last activity 12 minutes ago.”
2. **Full summary as text** in a popup / TUI, with optional “read first paragraph.”

If you later integrate with Polylogue’s local archive/search (SQLite/FTS + TUI), voice can become a query surface: “search my transcripts for ‘flake lock mismatch’.” fileciteturn35file0L1-L1

## NixOS deployment implications

### Where voice services should run in Sinnix

The vocal interface should be a **user service** tied to the graphical session, not a lingered always-on daemon, for two reasons:

- It depends on the user’s PipeWire session and on desktop feedback surfaces (Waybar/fnott). fileciteturn43file0L1-L1 citeturn1search2turn2search0
- Sinnix already uses the “graphical-session.target” pattern for other Wayland-centric services (clipboard, ActivityWatch watchers). fileciteturn42file0L1-L1 fileciteturn43file0L1-L1

### Hotkey binding and input routing

Hyprland keybindings are already the primary global input mechanism in Sinnix, and they include media keys and mic toggles, plus `notify-send` usage. This is the natural integration point for “start voice capture now.” fileciteturn45file0L1-L1

A practical binding pattern:

- Bind a key (example: `SUPER, M`) to execute `sx-voice capture --mode command`.
- The command temporarily unmutes mic (if configured), records until VAD end-of-speech, transcribes, shows parsed command in fnott, and executes on confirm.

You already have a mic toggle bound (`SUPER, XF86AudioMute`) and a shared `audio` script that manipulates `@DEFAULT_AUDIO_SOURCE@`. That makes it feasible to keep the mic muted by default and only unmute during capture windows. fileciteturn45file0L1-L1 fileciteturn48file0L1-L1

### PipeWire and device permissions on NixOS

NixOS’s PipeWire guidance emphasizes PipeWire’s low-latency capture/playback focus, broad compatibility, and its security model for capture (especially in sandboxed contexts). It also highlights the use of `wpctl` under WirePlumber as a high-level control tool. citeturn1search2turn1search6

Your existing scripts assume `wpctl` and `pw-dump`. That’s a solid baseline for device selection, mute control, and telemetry. fileciteturn48file0L1-L1

### Packaging models and caches

Local-first voice needs *stateful model data*:

- Whisper models (if using Whisper) and Piper voice models should live in an explicit cache directory under XDG or Sinnix state roots.
- Avoid hiding multi-hundred-MB models in ad-hoc locations; make them declarative: “which model size?” “which voice?” “where stored?” `piper-tts` and `whisper-cpp` are packaged, but model assets are separate and should be managed explicitly by your module. citeturn4search0turn3search13turn1search2

### Notifications: visual-first with optional speech

Sinnix uses fnott for notifications and exposes notification state in Waybar, including click-to-dismiss. This is ideal for voice UX:

- Always show recognized command + target session in a notification.
- Use short earcons/TTS only when severity warrants. fileciteturn43file0L1-L1 fileciteturn50file0L1-L1

Speech Dispatcher supports priorities and spelling mode via `spd-say`, which is a concrete mechanism to implement “quiet hours,” “progress vs critical,” and “spell it out” for tricky identifiers. citeturn4search17turn5search1

## Recommended design for Sinnix and first implementation slice

### Recommendation set

**Should Sinnix support voice at all?**
Yes—*but only* as (1) a command-and-control surface for session management and (2) an optional auditory notification channel. Voice dictation for code or arbitrary shell commands should not be the goal of this phase. This aligns with both the reliability constraints of STT and the operator’s desire for legibility and control. citeturn0news49turn3search9turn3search12

**Local-first vs hybrid**
Default to **local-first** for both STT and TTS. Add a **hybrid fallback path** (cloud STT/TTS) only as an opt-in “quality rescue” mode, since OpenAI’s APIs offer high-quality STT and low-latency voice interactions but are not local-first. citeturn3search8turn3search1turn3search0
Use the hybrid path only when the operator explicitly requests it (“use cloud transcription this time”).

**Best-fit interaction model**
Implement “hotkey-gated one-shot capture” first, with strict command grammar and confirmations. This is the best fit for Hyprland + PipeWire + terminal-native workflows. fileciteturn45file0L1-L1 citeturn2search0turn2search2

### First implementation slice

A minimal but real “voice command palette” for session control:

**Operator flow: voice-driven session attach**

1. Press hotkey (e.g., `SUPER+M`).
2. Hear a short beep; Waybar (or a notification) shows “Listening…” (optional). fileciteturn50file0L1-L1
3. Speak: “attach auth one.”
4. STT returns text; parser maps it to a structured action: `attach session=auth-one`.
5. fnott notification shows:
   - Recognized command: “attach auth-one”
   - Target session: auth-one
   - Buttons: Confirm / Cancel
6. On confirm, execute the existing attach flow (open terminal viewport, attach/observe).

**Operator flow: voice-driven interrupt**

1. Hotkey → “Listening.”
2. Speak: “stop current session.”
3. Notification shows: “Stop session <active>? Confirm.”
4. Confirm via voice (“confirm”) or second hotkey press.

**Operator flow: status query with spoken readback**

1. Hotkey → speak: “status auth one.”
2. System runs status command; shows full output in notification; optionally speaks one sentence: “auth-one is waiting for approval” (or “auth-one is running”).
3. If multiple sessions, it speaks: “Two matches. Check the popup.”

### Implementation scaffolding

A clean factoring is:

- `sx-voice` CLI tool (invoked by Hyprland hotkey).
- `sx-voiced` user service (optional) for shared model warmup, device selection, and future “always-on” experiments; tie it to `graphical-session.target`. fileciteturn42file0L1-L1 fileciteturn43file0L1-L1
- A small state file (or DB) to store:
  - last recognized command,
  - last target session,
  - microphone device and mute restoration policy,
  - failure counters (for debugging).

Suggested local stack for slice 1:

- Audio capture: `pw-record` (PipeWire) into a temp WAV/PCM. citeturn2search0
- VAD: WebRTC VAD to detect end-of-speech reliably with low compute. citeturn2search2
- STT: `whisper-cpp` default. citeturn4search0
- Feedback: fnott notifications + optional `spd-say` for short acknowledgements. fileciteturn43file0L1-L1 citeturn4search17turn5search1

### What should remain keyboard-first

- Editing code, selecting precise text, applying patches.
- Any operation requiring high precision and high bandwidth (paths, flags, complex commands).
- Bulk management tasks where an fzf-like UI is faster than voice.

### Do not build yet

This section is intentionally explicit.

- **Wake word / always-listening mode** as the default. Even with local openWakeWord and NixOS Wyoming support, always-on listening introduces high accidental activation and attention costs, and it’s difficult to make “pleasant day-to-day” on a workstation. citeturn2search3turn5search18turn5search15
- **Voice-driven execution of arbitrary shell commands** (“run rm -rf …”): too risky given STT errors and reported confabulation behaviors; keep voice actions constrained to a safe command set with confirmations. citeturn0news49
- **Full duplex conversational mode** as the primary interface. It is easy to demo, hard to live with, and tends to increase cognitive load for ops-style workflows. citeturn3search0turn3search2
- **“Voice coding” as a product goal** unless you’re explicitly committing to something like Talon as your daily driver. Talon succeeds via a full ecosystem: command/dictation/sleep modes, global hotkeys, and extensive per-app grammar. That’s a separate multi-month commitment. citeturn3search5turn3search9turn3search12

## Risks, anti-goals, and open questions

### Key risks

- **Recognition errors causing destructive actions**: mitigated via strict grammars, confirmations, and always showing recognized text before execution. citeturn0news49
- **Noise and multi-speaker environments**: VAD helps, but reliability remains situational; you should treat voice as an optional accelerator, not required infrastructure. citeturn2search2
- **Latency and “feel”**: if local STT takes too long, the interface will be abandoned. Vosk’s streaming orientation might outperform Whisper for short command grammars; this motivates an eventual Vosk engine for command mode. citeturn1search0turn1search7
- **Privacy posture**: even local capture can be uncomfortable if the mic is “always open.” Your existing ability to toggle mic mute at the system level supports a strong default posture. fileciteturn48file0L1-L1

### Anti-goals for this phase

- Not building a general voice assistant for the whole desktop.
- Not designing voice-driven file/system modifications beyond session control.
- Not building remote/mobile control planes (mention only as future hooks).

### Open questions to resolve with small experiments

- Does `whisper-cpp` on your hardware yield acceptable end-to-end latency for 1–3 second voice commands? (Measure: hotkey→result). citeturn4search0
- Is Vosk accuracy good enough for your command grammar and language mix (English commands, possibly Polish accent)? Vosk supports many languages and has vocabulary adaptation mechanisms. citeturn1search0turn1search7
- Is Speech Dispatcher’s voice quality acceptable for short alerts, or do you want Piper for all spoken output? Nixpkgs has both `speech-dispatcher` and `piper-tts`, and even a Piper manager for Speech Dispatcher (`pied`). citeturn5search1turn3search13turn5search11
- Do you want “mic muted by default; auto-unmute during capture and restore” as a hard invariant? This is feasible given your PipeWire tooling. fileciteturn48file0L1-L1

## Appendix: sources with links and dates

All sources accessed on **2026-03-19** unless noted.

### Sinnix repo context

- Hyprland bindings and audio key integrations (mic toggle binding; notify-send usage). fileciteturn45file0L1-L1
- PipeWire audio management script (`wpctl`, `pw-dump`, mic toggle). fileciteturn48file0L1-L1
- Desktop base: fnott notifications, tofi launcher, graphical-session user service patterns. fileciteturn43file0L1-L1
- Waybar module showing notifications/audio state and custom scripts. fileciteturn50file0L1-L1
- Input pipeline / interception tools logging context “hyprland” (useful for future hold-to-talk experiments). fileciteturn41file0L1-L1
- Hyprland module using UWSM + portal package choices (session-managed Wayland). fileciteturn51file0L1-L1

### STT / VAD / wake word

- OpenAI Whisper announcement (official). citeturn0search3
- Whisper paper reference page. citeturn0search13
- Whisper hallucination / confabulation concerns reported in investigation coverage (2024-10-30). citeturn0news49
- MyNixOS: `whisper-cpp` package (v1.8.2). citeturn4search0
- MyNixOS: GNOME extension “speech2text-with-whispercpp” (local STT with keyboard shortcut UX). citeturn4search1
- Vosk official site and capabilities (offline, streaming API, vocabulary tuning). citeturn1search0turn1search7
- Vosk PyPI package page (offline STT toolkit overview). citeturn0search4
- WebRTC VAD PyPI page (frame constraints, aggressiveness modes). citeturn2search2
- openWakeWord PyPI page (streaming frame size model, confidence output, false accept/reject goals). citeturn2search3
- NixOS / MyNixOS: `wyoming-openwakeword` and NixOS options (`enable`, `threshold`, `package`). citeturn5search18turn5search15turn5search13

### TTS and notifications

- Speech Dispatcher package + executables in nixpkgs (v0.12.1). citeturn5search1
- `spd-say` man page (priority classes, spelling, punctuation modes). citeturn4search17
- MyNixOS: `piper-tts` package (v1.3.0). citeturn3search13
- PyPI: `piper-tts` release history showing newer versions (e.g., 1.4.1 released 2026-02-05). citeturn1search3
- MyNixOS: `pied` (Piper voice manager for Speech Dispatcher). citeturn5search11

### Audio capture and PipeWire on NixOS

- PipeWire CLI manual for `pw-cat` / `pw-record` (PipeWire 0.3.52 man page snapshot). citeturn2search0
- PipeWire documentation index (program pages). citeturn2search6turn2search18
- NixOS Wiki: PipeWire configuration and model notes (extraConfig from 24.05+, WirePlumber usage, `wpctl`). citeturn1search2

### Voice interaction UX prior art

- Talon official docs (`.talon` files define voice commands and global hotkeys). citeturn3search5
- Talon community wiki: mode switching (command/dictation/sleep) and rationale. citeturn3search9turn3search12

### Optional hybrid voice APIs

- OpenAI blog: Realtime API introduction (speech-to-speech; persistent realtime connection). citeturn3search0
- OpenAI docs: Speech-to-text endpoints and supported models. citeturn3search8
- OpenAI docs: Text-to-speech endpoint and voice options. citeturn3search1