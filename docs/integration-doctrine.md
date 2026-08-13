# Integration doctrine: sinnix / sinex / lynchpin / polylogue

> Decided 2026-08-11 with the operator (`sinnix-cty`). This is the standing
> split of responsibility across the four repos in the constellation that
> handle capture and analysis. Read this before adding a capture lane or an
> analysis product to any of them — it decides which repo it belongs in.

## Principle

Irreversibility rules priority. Uncaptured data is the only permanent loss;
analysis is replayable later over stored raw. Every sequencing decision below
follows from this.

## The split

- **sinnix** owns machine + capture daemons + model-serving endpoints. This is
  where new capture lanes land, full stop — see `pkgs/sinnix-capture/` for the
  shared envelope convention every lane should use.
- **polylogue** owns the AI-session organ (Claude/Codex/Gemini/agent history).
- **sinex** owns the event substrate + semantic layer — the eventual absorber
  of everything currently interim in lynchpin.
- **lynchpin** is INTERIM analysis: thin, replaceable, no new architecture
  investment. It exists to be dissolved once sinex's semantic layer lands.

## Rules

1. Capture programs (screen/terminal/web capture, dbus/MPRIS/AT-SPI singles,
   and every capture lane like it) land in **sinnix now**, as dumb-durable
   units writing raw + JSONL to the lake in standard formats — never
   sinex-specific schemas (see the `no-sinnix-specific-workload-APIs`
   standing memory: standard envelopes only). Sinex ingests by replaying
   stored raw later; capture is never redone for sinex's benefit.
2. New analysis work (menus, census-style outputs) must be lake-in/lake-out
   portable, so it survives lynchpin's eventual dissolution without a
   migration project.
3. Lynchpin investment stays restricted to P1-severity work and the
   silent-coverage-collapse failure class (the same family as `sinnix-e8e`) —
   nothing structural. Don't build new architecture there.
4. Sinex's first-user-mile (tracked in sinex's own repo) outranks any
   alternative-path building elsewhere in the constellation — every interim
   capability built around sinex's absence deepens the moat and makes the
   eventual absorption harder, not easier.

## Sequence

Capture-first, sinex-mile second, lynchpin repairs opportunistic — in that
priority order when work across the constellation competes for attention.

## Where polylogue's own scope stops

Polylogue stays an evidence plane, not a general assistant. In scope:
semantic search over its own AI-session archive; cross-session derived
products that are session-scoped (topic threads, a decision index answering
"what did we decide about X" with line citations, per-project conversation
timelines); the estate's conversational-memory MCP surface. Anything shaped
like a general RAG-over-notes assistant, scheduled research automations, or
editor plugins is out of scope for polylogue specifically — those are a
different capability, if ever built.
