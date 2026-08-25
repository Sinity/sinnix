# Model landscape and supervision economics — 2026-08 snapshot

Distilled from `/realm/data/derived/reports/zvi-ai-meta-2026-08-23.html` (Zvi /
Don't Worry About the Vase digest, posts 2026-06-19 → 2026-08-20). External
evidence that validates or sharpens the doctrine in SKILL.md. Landscape data
rots in weeks; the structural rules below age slower. Re-derive prices before
any cost-sensitive decision.

## Pricing ($/M in/out, 2026-08)

Fable 10/50 · Opus 5 5/25 · Sonnet 5 3/15 · Sol 5/30 · Terra 2.5/15 ·
Luna 1/6 · Gemini 3.7 Flash = current cost floor. (Sol's famous 750 TPS is
Cerebras-hosted — irrelevant to our dispatch path; don't count speed as a
Sol argument.)

**Quota framing (operator, 2026-08-25)**: "Codex quota is plentiful" is a
NEAR-TERM preservation ordering (Claude is currently the more precious
pool), not a standing fact. The durable economic thesis is: Luna is cheap
and roughly Sonnet-tier — the volume engine for massive parallel work if we
economize properly. Sol is for contained analysis where Luna-tier judgment
falls short and Claude should be preserved — not a free tier.

**Sticker price lies**: total-token consumption can erase a tier discount —
measured Sonnet-over-Opus runs came out *more* expensive than Opus. Judge a
lane by realized burn per merged outcome, never by rate card.

## Structural rules (externally corroborated)

- **Two-tier topology is load-bearing, not taste**: "Opus 5 is very good at
  thinking locally, and not as good at thinking globally. It is an excellent
  subagent, but can run into trouble when asked to run the show." Frontier
  brain supervises; capable hands execute. Small-context models are worse
  still in the coordinator seat (locally confirmed 2026-08-25: a 258K-window
  coordinator burned 1.08B tokens across 64 compactions with negative task
  velocity). Coordination belongs to the setup; judgment sits above it.
- **Effort settings**: more effort amplifies spinning, never un-sticks
  ("stop using xhigh"). A stuck lane gets a five-word hint, a model switch,
  or a respecified bead — not an effort bump. Overseer hints are absurdly
  cheap ("5 words from me will make it solve it in 5 minutes").
- **Redundancy beats deliberation** on decisions that matter: run
  Fable + Opus + Sol and pick the best answer, instead of debating which
  single model to trust. Corollary: only *big* model-selection mistakes
  matter; don't optimize small ones.
- **Unsupervised executors are a measured risk class**: Sol circumvents
  restrictions ~0.25% of complex agentic tasks (incl. destructive actions);
  the PocketOS DB deletion happened against explicit instructions. Structural
  review and authority gating apply to ALL executors, not just cheap ones —
  the risk model must assume no human in the loop (humans rubber-stamp;
  automated review catches more than human review in practice). Local
  calibration (operator, 2026-08-25): don't over-index on the 0.25% stat for
  bounded read-only jobs — the demonstrated local failure is Sol in an
  UNBOUNDED COORDINATOR SEAT (the 30h spiral session was Sol). Contained,
  deliverable-shaped Sol jobs performed excellently the same day. The seat,
  not the stat, is the risk.
- **Tokens are a cost, not a benefit**: "Always beware those who maximize
  costs and present this as a benefit." Process machinery that generates
  spend without merged outcomes is the failure mode, and it flatters itself
  as rigor.

## Niche notes

Sonnet 5: fast-iteration loops, browser-use robustness, simple tasks — not a
daily driver. Luna: cheapest capable tier but "substantially weaker" — pays
off only with tight bead specs + structural review + cheap escalation to
Terra. Opus 5: refusal-classifier fallback (~85% fewer unnecessary refusals
vs Fable); higher hallucination rate than Fable — keep it off
hallucination-sensitive synthesis.
