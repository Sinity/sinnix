# Integrating Local Coding-Agent Operations With Sinex as Exocortex

## Executive summary

This phase-3 pass finds that **Sinex is worth making central to the “system-of-record” side of local coding-agent operations**—but only if it is treated as an **event/provenance substrate + query layer**, not as a brittle interactive “control brain.” The most implementation-sound split is:

- **sinnix owns control, orchestration, session UX, and “make it run on NixOS” plumbing** (starting sessions, attach/detach, per-project conventions, keybinds, operator flows).
- **sinex owns durable memory, structured observability, provenance, indexing, and replay-friendly retention** (events + source material registry + lifecycle). This is aligned with Sinex’s existing architecture: events with explicit provenance, a dedicated source-material registry, and a principled lifecycle model (live → archive → tombstone). fileciteturn27file0L1-L1 fileciteturn28file0L1-L1 fileciteturn30file0L1-L1 fileciteturn89file0L1-L1

The practical “win condition” is that **agent sessions become legible across time and across many concurrent sessions**:
- You can ask: “what is every agent doing?” without attaching to each session.
- You can trace: “why did this code change happen?” back through prompt → tool calls → file edits → approvals → final outcome, using provenance chains rather than ad-hoc correlation IDs.
- You can enforce retention/privacy policies with a real lifecycle model rather than “delete some logs and hope.” fileciteturn89file0L1-L1 fileciteturn93file0L1-L1

**Voice integration (from phase 2)** can mesh well with Sinex *as an observational truth store* (voice commands and results as events, plus voice-driven status queries answered from structured state). But **Sinex should not be the first-hop dispatch point for interactive control**; the safest first integration is “voice → sinnix control plane,” while **Sinex receives an audit/event stream** of voice command intent, disambiguation, confirmations, and actions taken. The privacy-security design explicitly treats audio and transcripts as high-sensitivity and emphasizes private mode and principled retention. fileciteturn93file0L1-L1

A key finding is that the repos already contain **most of the infrastructure needed to do this cleanly**:
- sinnix already has structured terminal session capture (asciinema + JSONL “command_start/command_end” events) and workspace metadata that can be linked to agent sessions. fileciteturn111file0L1-L1 fileciteturn112file0L1-L1
- sinnix already has a systemd-user scheduled ingest service for polylogue with explicit resource controls (Nice/IOSchedulingClass/MemoryHigh/MemoryMax), a strong precedent for running “background ingestion” safely. fileciteturn115file0L1-L1
- sinnix already has a Sinex module that enables nodes/automata and a realm-root watch path, even if disabled on the primary host profile today. fileciteturn80file0L1-L1 fileciteturn81file0L1-L1
- Sinex already has: (1) a formal schema/provenance model, (2) an operator CLI (`sinexctl`) over a gateway RPC, (3) a JetStream-based ingestion/event bus, (4) terminal+Kitty event models, and (5) lifecycle operations. fileciteturn29file0L1-L1 fileciteturn31file0L1-L1 fileciteturn89file0L1-L1 fileciteturn101file0L1-L1

## Constraints and affordances inferred from sinnix and sinex

### sinnix already emits “high-value correlators” for provenance

sinnix’s captured-shell wrapper creates a **session directory per terminal session**, writes a `session.json`, and records an asciinema cast (`session.cast`) plus a JSONL stream of session events. It also exports environment variables that can carry through into child processes (including agent CLIs), such as `SINNIX_CAPTURE_SESSION_ID`, repo metadata, and project root. fileciteturn111file0L1-L1

The Zsh hooks append structured events like `session_start`, `command_start`, `command_end`, and `session_end` with timestamps, CWD, and repo/worktree context. This is already “event-shaped” data that can be transformed into Sinex events with explicit provenance roots. fileciteturn112file0L1-L1

**Implication:** For agent operations, you already have a stable *local session identity* and *repo context* that can become either:
- the **session/entity identity** in Sinex, or
- a strong linkage key between “agent session” and “terminal session,” enabling query: “show me agent work that happened in this shell session.”

### sinnix already has ingestion-as-a-service patterns (polylogue) suitable for Sinex adapters

The polylogue systemd user unit runs ingestion periodically (`polylogue --plain run`) and explicitly deprioritizes it (Nice=19, IOSchedulingClass=idle) and caps memory (MemoryHigh/MemoryMax). This shows sinnix already uses **“background ingestion must be safe”** patterns. fileciteturn115file0L1-L1

**Implication:** A “Sinex adapter/collector” for agent sessions can be deployed in the same style: either as a timer or as a long-running user service, without destabilizing interactive work.

### sinnix already contains a Sinex deployment module (even if disabled on the main host)

The sinnix `services/sinex.nix` module is non-trivial: it references a Sinex flake input, configures a realm root, watch paths, and enables a set of nodes/automata (filesystem, terminal, clipboard, system, plus canonicalizer and health aggregator), and has monitoring integration. fileciteturn80file0L1-L1

However, the primary host profile (`hosts/sinnix-prime/default.nix`) currently disables Sinex and polylogue, while enabling terminal capture. fileciteturn81file0L1-L1

**Implication:** Recommendations must support a path where:
- sinnix can run the agent UX layer even when Sinex is off, and
- Sinex integration can be enabled incrementally without re-architecting the session UX.

### Sinex’s architecture is explicitly built for provenance-preserving ingestion and replay

Sinex’s schema and docs emphasize:
- **Events are immutable records** with explicit provenance.
- Provenance is encoded as either `source_material_id` (raw ingested artifact root) *or* `source_event_ids` (derived from earlier events), but not both—designed to preserve derivability and replayability. fileciteturn30file0L1-L1
- A **source material registry** exists to track raw artifacts and support replay (“raw is more valuable than interpretation”). fileciteturn28file0L1-L1 fileciteturn78file0L1-L1
- A multi-tier lifecycle model exists (live/archive/tombstone) with cascade invariants to keep provenance chains internally consistent within a tier. fileciteturn89file0L1-L1

Sinex’s node SDK and messaging model show that ingestion and derived processing are built around **JetStream subjects** of the form `events.raw.<source>.<event_type>`, where source + event type jointly identify the event family. fileciteturn33file0L1-L1 fileciteturn66file0L1-L1

**Implication:** The cleanest modeling for coding-agent activity is to:
1. Emphasize **raw transcript artifacts** as source materials (files, JSONL, cast logs, provider exports).
2. Emit a normalized **event stream** derived from those artifacts (session state transitions, turns, tool invocations, approvals), with provenance pointing back to source materials.

### Sinex already models terminal and Kitty state in a way that can anchor agent-session “viewports”

Sinex includes schemas and payloads for Kitty sessions and tab focus. fileciteturn83file0L1-L1 fileciteturn84file0L1-L1 fileciteturn85file0L1-L1 These are important because “attach/detach” and “multi-viewport” become much easier if you can connect:
- agent session ↔ tty/terminal session ↔ Kitty tab/window events.

The `crate/lib/sinex-primitives` shell payload module shows Sinex already has a rich terminal event model including Kitty command events, tab focus, scrollback output capture, and asciinema session start/end. fileciteturn65file0L1-L1

**Implication:** Do not invent a new “viewport identity system” in the exocortex. Instead:
- treat “viewports” as **terminal/window artifacts** already captured by Sinex nodes (Kitty/session events), and
- link them to agent sessions via session IDs and environment linkage.

### Sinex has an operator CLI and an extensible gateway method registry

`sinexctl` is explicitly an operator CLI with gateway RPC as the primary path, plus direct-DB diagnostics, and it emphasizes explicit operator intent for destructive flows. fileciteturn87file0L1-L1 fileciteturn88file0L1-L1

The gateway RPC registry is built around a method namespace scheme and role-based permissions (ReadOnly/Write/Admin), including `events.query`, `events.lineage`, and `events.ingest`. fileciteturn101file0L1-L1

**Implication:** “Agent ops” can be added either by:
- shipping a new `sinexctl agent …` command group that is just a specialized query layer over existing events, and/or
- adding a small set of new gateway methods that return “materialized session summaries” efficiently (without requiring clients to re-derive state every time).

### sinex-target-vision explicitly prioritizes raw material and replayable interpretations

The canonical vision says raw sources are more valuable than derived interpretations and stresses rebuildability via replay. fileciteturn78file0L1-L1

**Implication:** For coding-agent operations, resist the temptation to store only “pretty summaries.” Store:
- raw transcripts (or at least raw-enough artifacts) as source materials,
- normalized structured events derived from those,
- optional summaries/embeddings as derived layers that can be regenerated.

### polylogue is already a transcript normalizer across providers, and it already targets Codex session JSONL

polylogue’s Codex provider docs and parser show it already:
- ingests Codex JSONL sessions,
- detects multiple format generations,
- extracts git context and system instructions when present,
- models parent conversation IDs (branch/continuation). fileciteturn95file0L1-L1 fileciteturn96file0L1-L1

sinnix also contains evidence of a real-world Codex sessions directory convention at `~/.codex/sessions/YYYY/MM/DD/…jsonl`, which is an obvious ingestion target for both polylogue and Sinex. fileciteturn114file0L1-L1

**Implication:** polylogue can serve as:
- an interim “normalization layer” whose output is ingested into Sinex, or
- a reference implementation/design seed for a Rust-native Sinex ingestor later.

## Role options for sinex

The key architectural decision is how “active” Sinex should be in agent operations. The table below rates *roles* for Sinex within the combined system.

| Sinex role option | Alignment | What you get | What it costs / risks | Recommendation |
|---|---|---|---|---|
| Passive archive only (store transcripts) | Plausible but risky | Minimal integration effort; “search later” | Leaves legibility/dashboarding to ad-hoc tools; weak provenance; hard to answer “what’s happening now?” | Useful as a fallback mode only |
| Observability/event ingestion layer | Strongly aligned | Durable, queryable event history; provenance; replay; consistent schema validation | Need careful event taxonomy + adapter code | **Yes: foundational** |
| Transcript index + retrieval (FTS/embeddings) | Strongly aligned (with constraints) | Cross-session search; semantic retrieval; operator queries | Must handle sensitivity/retention; embeddings pipeline is still implementation work | Yes, but phase after ingestion is solid |
| State mirror of agent sessions (materialized “current state”) | Strongly aligned if bounded | “What’s running/blocked?” queries are fast; dashboards easy | Risk of duplicated state logic; must define “truth” rules | Yes, but keep it derived from events, not authoritative control logic |
| Control-plane participant (dispatch commands) | Plausible but risky | Unified control surface; voice-to-command routing via RPC | High coupling; failure modes are scary; auth/permissions become high-stakes | Only for narrow, non-interactive controls (e.g., “request summary”), later |
| Automation trigger engine (event-driven workflows) | Plausible but risky | Auto-notify on blocked sessions; periodic summarization; hygiene tasks | Easy to over-automate; surprises; must be inspectable | Later; start with notification-only automations |
| Long-term memory / exocortex layer | Strongly aligned | “Narrative continuity,” provenance-aware summaries, longitudinal traces | Privacy/retention becomes critical; storage growth | Yes, but only with lifecycle + privacy design applied |
| Unified query layer across sessions/repos/operator activity | Strongly aligned | The “real exocortex” payoff: queries across terminal, files, agent turns, approvals | Needs consistent IDs and linking across sources | Yes; it is the “why Sinex” justification |

This scoring is directly supported by Sinex’s existing foundations: provenance constraints and lifecycle operations are not bolt-ons—they are core. fileciteturn30file0L1-L1 fileciteturn89file0L1-L1

## Proposed domain model and event taxonomy

### Modeling principle: do not conflate session identity with viewport identity

- **Session identity**: “the thing the agent is doing” (task context, turn sequence, tool invocations, approvals).
- **Viewport identity**: “where a human sees/controls it” (Kitty windows/tabs, tmux panes, remote attaches).

Sinex already captures viewport-adjacent data for terminals (Kitty sessions, focus changes), and sinnix’s terminal capture has a stable session ID that can be propagated into agent processes. fileciteturn65file0L1-L1 fileciteturn111file0L1-L1 fileciteturn112file0L1-L1

**Recommendation:** Treat viewports as *linkable context* captured by terminal nodes; model agent sessions as top-level entities/events, linked to terminal sessions when relevant.

### Concrete entity model in Sinex

Sinex already includes an entity registry and relations (knowledge-graph-ish), and the gateway exposes PKM methods for entity creation/linking. fileciteturn28file0L1-L1 fileciteturn101file0L1-L1

Define these conceptual entities (as Sinex entities + relations):

- **AgentSession**: stable ID, provider, model, repo/worktree context.
- **AgentThread**: conversational thread within a session (or a provider session ID).
- **AgentTurn**: a single “cycle” of agent reasoning and tool calls.
- **Viewport**: Kitty tab/window ID, tty, or remote attach handle (treated as external context).
- **Task**: human task title, optionally linked to repo/worktree, issue ID.
- **Approval**: approval-required checkpoint, who approved, what was approved.
- **Artifact**: raw transcript files, asciinema casts, tool logs, diffs, generated patches.

### Event taxonomy proposal

Use Sinex’s event naming approach: define a **source** for the emitting component (likely the agent-ops adapter/daemon) and an **event_type** for the事件. Sinex’s NATS subject scheme expects `events.raw.<source>.<event_type>`. fileciteturn66file0L1-L1

A practical approach is:
- `source = agent.ops` (or `agent.sinnixd`) for the adapter that emits normalized agent events.
- `source = voice.ops` for voice-driven interactions (if/when enabled).
- Reuse existing sources for terminal viewports (`terminal.kitty`, `shell.kitty`) rather than duplicating them. fileciteturn83file0L1-L1 fileciteturn85file0L1-L1

#### Proposed event classes and why they exist

| Event class (source + event_type) | Emits from | Provenance root | Why it exists / what it enables |
|---|---|---|---|
| `agent.ops` + `session.started` | sinnix agent runner/adapter | Source material: “session manifest” (JSON) | Base identity + initial metadata; enables “list sessions” |
| `agent.ops` + `session.ended` | agent runner/adapter | Source material: session manifest + terminal capture | Explicit lifecycle; enables retention and “archived vs active” |
| `agent.ops` + `thread.created` / `thread.forked` | adapter (provider-aware) | Source material: provider session JSONL (e.g., Codex export) | Captures branching/continuation semantics (polylogue already extracts parent IDs for Codex) fileciteturn96file0L1-L1 |
| `agent.ops` + `turn.started` / `turn.completed` / `turn.interrupted` | adapter | Derived from transcript + tool logs | Turn boundaries enable summaries, performance metrics, blocked-state detection |
| `agent.ops` + `blocked.on_input` / `blocked.on_approval` | adapter or runtime | Derived from runtime state | Enables dashboards and notifications without attaching |
| `agent.ops` + `tool.invocation.started` / `tool.invocation.completed` / `tool.invocation.failed` | adapter/runtime | Source material: tool log blob | Core for provenance: “prompt → tool → output → code change” |
| `agent.ops` + `transcript.item_emitted` | adapter | Source material: transcript file | Enables indexing/search and incremental summaries |
| `agent.ops` + `summary.generated` | sinex automaton or external summarizer | Derived from transcript items | Must be replayable/replaceable; not a primary root |
| `agent.ops` + `viewport.attached` / `viewport.detached` | sinnix control surface | Derived from terminal events | Encodes “who is controlling,” multi-view semantics |
| `voice.ops` + `command.received` / `command.interpreted` / `command.confirmed` / `command.executed` | voice layer + sinnix control | Source material: (optional) audio clip + STT transcript | Provides auditability and error recovery for voice control; supports “what did I say?” |
| `voice.ops` + `query.asked` / `query.answered` | voice layer + sinex query | Derived from sinex state | Enables voice status queries with structured answers |

This table is consistent with Sinex’s preference for replayable derivation: the “raw thing” is a source material; “normalized event” is derived. fileciteturn78file0L1-L1 fileciteturn30file0L1-L1

### Key provenance rule: store “raw enough” to replay

Sinex’s schema design explicitly pushes toward:
- Source materials representing raw inputs,
- Derived events that can be regenerated from those roots. fileciteturn30file0L1-L1 fileciteturn28file0L1-L1

For agent operations, “raw enough” usually means:
- provider-native session JSONL (e.g., Codex session logs under `~/.codex/sessions/...jsonl`) fileciteturn114file0L1-L1
- terminal captures (asciinema casts + sinnix command JSONL) fileciteturn111file0L1-L1 fileciteturn112file0L1-L1
- tool invocation logs (structured if possible)
- optional diffs/patches or a commit hash when actions are applied

## Architecture options and tradeoff table

The main architectural spectrum is: “Sinex as observation substrate” vs “Sinex as interactive control plane.” The recommended approach is intentionally biased toward observation-first.

### Architecture comparison

| Architecture option | Implementation complexity | Fidelity | Coupling risk | Replayability | Observability quality | Operator UX benefit | Recommendation |
|---|---:|---:|---:|---:|---:|---:|---|
| File-first in sinnix + Sinex adapter (sidecar ingestion) | Medium | High | Low | High | High | High | **Preferred** |
| Direct event emission from agent runtime into Sinex (JetStream/native) | High | Very high | Medium–high | High | Very high | High | Viable later (after event taxonomy stabilizes) |
| Polylogue-first → Sinex ingestion from normalized conversation DB | Medium | Medium–high | Medium | Medium (depends on what raw is preserved) | Medium–high | Medium | Good as “import path,” not as the only live path |
| Sinex becomes command dispatch/control mediation layer | Very high | N/A | High | N/A | Medium | Potentially high | **Do not start here** |

#### Why the preferred option wins

**File-first + adapter wins** for the current repo reality:
- sinnix already captures terminal sessions to disk with structured session IDs and metadata (excellent ingestion roots). fileciteturn111file0L1-L1 fileciteturn112file0L1-L1
- sinnix already runs scheduled ingestion workloads safely (polylogue service patterns). fileciteturn115file0L1-L1
- Sinex already has an operator/gateway interface for ingest and query (`events.ingest`, `events.query`, `events.lineage`). fileciteturn101file0L1-L1
- Sinex’s schema and lifecycle are built for ingesting raw roots and deriving events from them; the adapter approach keeps replay possible without tight coupling. fileciteturn30file0L1-L1 fileciteturn89file0L1-L1

The adapter can emit events into Sinex via the gateway (`events.ingest`) and register raw artifacts as source materials/blobs via existing content methods. fileciteturn101file0L1-L1

### Where schema management fits

Sinex supports “schema GitOps,” meaning new event schemas can be delivered from a git repo and pulled by ingestd. fileciteturn98file0L1-L1

**Recommendation:** Put coding-agent event schemas in **Sinex’s schema repo** (initially the sinex repo itself under `schemas/v1/...`), to keep validation and evolution in one place; optionally use GitOps if you want to iterate schemas from sinnix first.

## Voice-to-exocortex integration analysis

### What Sinex should do for voice, specifically

The privacy-security design for Sinex treats **audio transcripts as HIGH sensitivity** and proposes:
- raw audio stored as encrypted blob (mandatory),
- transcript processed through a document-oriented privacy context,
- transcripts not indexed in FTS by default (opt-in). fileciteturn93file0L1-L1

This maps cleanly to a voice-driven agent ops layer:

1. **Voice is a control surface and an audit stream**, not a magical assistant.
2. Voice commands should be captured as **events** with:
   - recognized text,
   - confidence,
   - resolved target session,
   - confirmation step for destructive actions,
   - execution outcome (success/failure + reason).  
   This directly supports “error recovery UX” and “why did it stop that session?” investigations. fileciteturn93file0L1-L1

### Observation vs control boundary for voice

Sinex already has operator-intent patterns for destructive operations (e.g., lifecycle tombstone is multi-step and role-gated). fileciteturn89file0L1-L1 fileciteturn101file0L1-L1

**Recommendation:** Mirror that philosophy for voice:

- **Voice layer → sinnix**: interpret command and dispatch to local agent/session manager (the “thing that actually does it”).
- **Voice layer → sinex**: record intent, disambiguation, confirmation, and result as events; store audio only when explicitly enabled.

This yields:
- auditability without building a fragile “Sinex voice dispatcher,”
- the ability for voice to query Sinex (“what’s blocked?”) using structured state,
- a consistent privacy and retention story anchored in Sinex lifecycle operations. fileciteturn89file0L1-L1 fileciteturn93file0L1-L1

### Voice data retention and deniability

The privacy-security design proposes that **private mode state should not be stored in core events** for deniability, and it emphasizes explicit retention defaults by source category. fileciteturn93file0L1-L1

**Recommendation for voice + agent ops:**
- Treat “voice audio clips” as *optional* and default-off (especially in shared spaces).
- Treat “voice command text” as an event stream subject to privacy engine processing.
- Consider storing **only command intent** (normalized) by default, not raw transcript, unless the user opts in to “keep what I said verbatim.”

### How voice queries become valuable through Sinex

Sinex’s value is that you can answer voice queries by reading from a structured state mirror:
- “Which sessions are blocked?”
- “Summarize the last 10 minutes of session X.”
- “Did any agent modify file Y today?”
- “What did I approve recently?”

This demands:
- agent session state events (`blocked.on_approval`, `turn.completed`),
- linkage to repo/worktree and filesystem events,
- consistent IDs, which Sinex’s provenance model is designed to support. fileciteturn28file0L1-L1 fileciteturn30file0L1-L1

## Recommended design

This section synthesizes the above into a decision-ready design that fits the repo reality as of 2026-03-19 (Europe/Warsaw).

### Design goals restated as “Sinex leverage”

Sinex is only worth integrating if it yields leverage beyond “logs on disk.” The leverage targets are:

- **Cross-session legibility** (what is each agent doing; who is blocked)
- **Causal provenance** (prompt/tool/output/file/commit lineage)
- **Durable memory** (search, summaries, embeddings) with replayability
- **Operator trust** (privacy mode, retention, explicit destructive flows) fileciteturn89file0L1-L1 fileciteturn93file0L1-L1

### Split of responsibilities

**Keep in sinnix (deployment/control surface):**
- Starting/stopping agent sessions, attaching/detaching, naming conventions.
- Terminal UX primitives (kitty commands, tmux/zellij workflows) and hotkeys.
- The adapter that converts local artifacts into Sinex events (at least initially).
- Voice capture and command interpretation (when enabled), because this is tightly coupled to device routing and operator preference.

**Move into / implement in Sinex (exocortex substrate):**
- Event schemas for agent operations (validated, versioned).
- A minimal “agent ops” derived state: views or projections that answer “current sessions and status.”
- Indexing layers (FTS/embeddings) for agent transcript items once the embedding pipeline is implemented.
- Lifecycle policies for agent transcripts/tool outputs, integrated with cascade archive/tombstone semantics. fileciteturn89file0L1-L1

### The ingestion pattern

1. **Local artifact roots** created by sinnix and agent tools:
   - terminal capture session directory (`session.json`, `events.jsonl`, `session.cast`) fileciteturn111file0L1-L1 fileciteturn112file0L1-L1
   - Codex provider session JSONL (`~/.codex/sessions/...jsonl`) fileciteturn114file0L1-L1
   - optional scrollback capture outputs (`/realm/data/captures/kitty-scrollback/*.ansi` + `.meta.json`) fileciteturn108file0L1-L1
   - polylogue normalized DB and exports (as a secondary source)

2. **Adapter/collector emits into Sinex**:
   - registers the artifact as a source material root (blob or file reference),
   - emits normalized events whose provenance points to that source material,
   - optionally emits derived events for summaries or status snapshots.

This respects Sinex’s “raw is more valuable than interpretation” stance. fileciteturn78file0L1-L1

### How polylogue should relate (near-term and future)

Near-term (pragmatic):
- polylogue remains a scheduled ingest tool that normalizes provider sessions; it is already deployed this way in sinnix. fileciteturn115file0L1-L1
- A Sinex adapter can ingest:
  - directly from provider session directories (Codex JSONL), *and/or*
  - from polylogue’s normalized outputs when provider formats are annoying or unstable.

Mid-term (if rewritten into Rust, as hinted):
- polylogue’s provider-normalization logic becomes a **Sinex-native ingestor node** or a shared “conversation normalization” crate used by Sinex nodes.
- The current polylogue Codex parsing logic—format detection, git metadata extraction, parent session linking—is a concrete blueprint for a Rust implementation. fileciteturn95file0L1-L1 fileciteturn96file0L1-L1

### Data retention / privacy classes for agent ops and voice

Sinex’s lifecycle model (live/archive/tombstone) and privacy-security design provide explicit guidance for sensitive streams, including audio and terminal commands. fileciteturn89file0L1-L1 fileciteturn93file0L1-L1

Recommended classes for coding-agent operations:

| Data class | Sensitivity | Default storage | Default indexing | Default retention approach |
|---|---:|---|---|---|
| Agent transcript text (prompt/assistant) | High | Event payload + (optional) raw transcript source material | FTS: yes (post-privacy); embeddings: later/opt-in | Live → Archive (project value); tombstone by policy |
| Tool invocation inputs/outputs | High–critical (may contain secrets) | Prefer source material blob + redacted event summary | FTS: careful; embeddings: generally no | Shorter retention than transcript; aggressive redaction |
| Approval records (what was approved) | Medium–high | Event payload (structured) | Indexable | Longer retention (audit trail) |
| Session state transitions (started/blocked/ended) | Low–medium | Event payload | Indexable | Long retention (small and valuable) |
| Voice command audio clips | High | **Opt-in only** encrypted blob | Not indexed by default | Short retention (weeks/months), tombstone aggressively |
| Voice command transcript (raw) | High | Event payload (processed) | Not indexed by default unless opt-in | Medium retention; allow “store normalized intent only” |
| Voice command normalized intent (e.g., `stop session X`) | Medium | Event payload | Indexable | Long retention (audit without raw speech) |

This table aligns with the privacy-security analysis that audio capture is high sensitivity and that command/clipboard style data demands strong privacy processing and clear retention policies. fileciteturn93file0L1-L1

## Phased implementation plan

### Minimum viable integration slice

Build the smallest loop that proves Sinex leverage without over-committing:

1. **Emit agent session state events into Sinex** (`session.started`, `blocked.*`, `session.ended`) from a sinnix-managed adapter.
2. **Link those sessions to terminal capture sessions** via `SINNIX_CAPTURE_SESSION_ID` and repo/worktree metadata already emitted by sinnix. fileciteturn111file0L1-L1 fileciteturn112file0L1-L1
3. Add a `sinexctl` query wrapper (or a thin `sinnix agent list` command) that answers:
   - “show active sessions,”
   - “show blocked sessions,”
   - “show last activity for each session.”

This proves “dashboard without attaching,” which is the first real exocortex win.

### Next slice: transcript + tool events, still adapter-driven

4. Ingest provider transcript artifacts (Codex JSONL from `~/.codex/sessions`) as source materials and emit normalized `transcript.item_emitted` events. fileciteturn114file0L1-L1
5. Add minimal tool invocation event support (start/completed/failed) from whatever agent runtime metadata exists; where metadata is missing, start with coarse “tool used” markers and refine later.

### Add durable indexing only once ingestion is stable

6. Implement embeddings/search for transcript items using the embedding pipeline design (which currently notes schema exists but code is needed, plus Ollama service isn’t configured in sinnix). fileciteturn97file0L1-L1  
   Use entity["organization","Ollama","local model runtime"] as the local embedding backend if you adopt that design.

### Optional: voice integration tied to proven state queries

7. Only after “blocked sessions / status summary” works reliably via Sinex, add voice:
   - voice → sinnix dispatch,
   - voice events → Sinex audit stream,
   - voice queries answered from Sinex’s structured session state and recent events. fileciteturn93file0L1-L1

### What to prototype outside Sinex first

- A “session adapter” that tails local artifacts and emits events via gateway RPC (`events.ingest`) should be prototyped as a standalone tool, then absorbed into a Sinex node once the schema is stable. Sinex already has an explicit ingest method. fileciteturn101file0L1-L1

### Do not build yet

- **Do not make Sinex the interactive control dispatcher** for agent sessions in the first iterations. The gateway is role-gated and supports destructive operations; mixing that with low-latency interactive “stop/steer” commands would create failure modes and security/UX risks that are not justified while the event model is still evolving. fileciteturn101file0L1-L1
- **Do not store raw voice audio by default.** The privacy-security design treats audio as high sensitivity and recommends encrypted blobs + cautious indexing. fileciteturn93file0L1-L1
- **Do not depend on embeddings for core UX.** The embedding pipeline is designed but not yet implemented end-to-end; build “blocked sessions” and “recent activity” from structured events first. fileciteturn97file0L1-L1

## Risks, anti-goals, and validation experiments

### Primary risks

1. **Schema churn and adapter drift:** Provider session formats change; early over-modeling leads to fragile ingestion. polylogue already indicates multiple Codex JSONL generations and normalization complexity. fileciteturn95file0L1-L1 fileciteturn96file0L1-L1  
   Mitigation: store raw sessions as source materials; keep derived events minimal at first.

2. **Over-coupling control to exocortex:** Making Sinex dispatch interactive commands too early increases coupling and makes failures more dangerous.  
   Mitigation: keep control in sinnix; store actions in Sinex as audit events.

3. **Privacy failure modes (tool outputs, voice):** Terminal commands and tool outputs often contain secrets; audio capture has additional legal/ethical risk. The privacy-security design explicitly treats these as high sensitivity and emphasizes private mode and retention. fileciteturn93file0L1-L1  
   Mitigation: aggressive privacy engine processing, opt-in audio, explicit private mode semantics.

4. **Operator trust erosion due to “unknown capture”:** If the operator can’t tell what’s being recorded, they will disable it.  
   Mitigation: adopt private mode UX and retention policies as first-class, not “later enhancements.” fileciteturn93file0L1-L1

### Validation experiments

- **Experiment: “blocked dashboard without attach.”**  
  Run 5–10 concurrent agent sessions, induce approval blocks, and verify you can list blocked sessions from Sinex without opening terminals. Success requires: `blocked.on_approval` events + stable session IDs.

- **Experiment: provenance trace from prompt to file change.**  
  Pick a small code change and verify an operator can trace from the agent’s prompt (or turn) to tool invocation records and to filesystem change events already captured by Sinex nodes. This validates linking strategy across sources.

- **Experiment: retention + tombstone correctness.**  
  Archive and tombstone a session chain and confirm no live event references an archived/tombstoned one (cascade invariant). This validates lifecycle semantics for agent data. fileciteturn89file0L1-L1

- **Experiment: voice audit trail without storing audio.**  
  Enable voice intent logging (normalized intent + confirmations) and check you can reconstruct what happened without raw audio. This validates a privacy-preserving “voice as control surface” approach. fileciteturn93file0L1-L1

## Appendix: sources with links and dates

Primary sources inspected (all in entity["company","GitHub","code hosting platform"]; dates included where files state them explicitly):

- Sinex schema and provenance foundations: fileciteturn28file0L1-L1 fileciteturn30file0L1-L1  
- Sinex node SDK overview (JetStream ingestion + node patterns): fileciteturn31file0L1-L1  
- Sinex NATS subject model (naming + event routing): fileciteturn66file0L1-L1  
- Sinex CLI and gateway RPC method registry (operator model + auth roles + events.ingest/query/lineage): fileciteturn87file0L1-L1 fileciteturn88file0L1-L1 fileciteturn101file0L1-L1  
- Sinex lifecycle model (live/archive/tombstone, cascade invariant): fileciteturn89file0L1-L1  
- Sinex Kitty/terminal event schemas (viewport anchoring): fileciteturn83file0L1-L1 fileciteturn84file0L1-L1 fileciteturn85file0L1-L1  
- sinnix terminal capture implementation (asciinema + JSONL events + propagated env vars): fileciteturn111file0L1-L1 fileciteturn112file0L1-L1  
- sinnix Kitty scrollback capture script (local artifact to ingest): fileciteturn108file0L1-L1  
- sinnix polylogue scheduled ingestion service patterns: fileciteturn115file0L1-L1  
- sinnix Sinex module and current host-level enablement status: fileciteturn80file0L1-L1 fileciteturn81file0L1-L1  
- sinex-target-vision canonical stance on replayable derivations (“raw is more valuable”): fileciteturn78file0L1-L1  
- sinex-target-vision privacy/security design (created 2026-03-16): fileciteturn93file0L1-L1  
- sinex-target-vision embedding pipeline design (created 2026-03-17): fileciteturn97file0L1-L1  
- polylogue Codex ingestion docs and parser (provider format drift handling): fileciteturn95file0L1-L1 fileciteturn96file0L1-L1  
- sinnix evidence of Codex session JSONL storage paths (practical ingestion target): fileciteturn114file0L1-L1  
- Schema GitOps mechanism (how to ship new event schemas): fileciteturn98file0L1-L1