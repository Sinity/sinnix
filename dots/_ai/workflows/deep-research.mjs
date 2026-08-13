// deep-research: exhaustive multi-agent research pipeline (sinnix-nx0).
//
// Deliberately beyond commercial-product depth: hosted "deep research"
// products cap at 5-30 sources and one search strategy. This pipeline runs
// N parallel searchers with DISTINCT query strategies, fetches FULL TEXT of
// every source found (not a snippet), extracts claims with cheap local
// lanes, adversarially verifies each claim (refutation attempt, not just a
// confidence score), and synthesizes with a completeness critic that names
// what's still uncovered -- closing the loop the other reference
// implementations (GPT-Researcher, STORM, LangChain open_deep_research,
// Local Deep Research) don't: none of them join against this estate's own
// evidence planes (lake captures, polylogue AI-session history, lynchpin
// analysis products) or use beads as the native output format instead of a
// disposable report file.
//
// Studied before writing (per sinnix-nx0's own notes): GPT-Researcher's
// planner/parallel-executors/publisher split (closest architecture to this
// one), Stanford STORM's outline-first perspective-guided question asking
// (the completeness-critic stage borrows this shape), Local Deep Research
// as the fully-local reference point.
//
// Usage: Workflow({ name: "deep-research", args: { question: "...",
//   depthBudget: "standard" | "exhaustive", includeEstateEvidence: true } })
//
// depthBudget controls searcher count and verification-vote count, not
// corpus size -- corpus size is "everything found", uncapped, per the
// bead's explicit rejection of the 5-30-source commercial cap.

export const meta = {
  name: 'deep-research',
  description: 'Exhaustive multi-agent research: full-corpus fetch, adversarial claim verification, completeness-critiqued synthesis',
  whenToUse: 'A research question that needs beyond-commercial-depth coverage -- every source found gets full-text fetched and claim-verified, not sampled. Slower and more expensive than a single research agent; use for questions where missing a source is the failure mode, not for quick lookups.',
  phases: [
    { title: 'Search', detail: 'N parallel searchers, distinct query strategies' },
    { title: 'Fetch', detail: 'full-text fetch of every source found, uncapped' },
    { title: 'Extract', detail: 'claim extraction via cheap lanes' },
    { title: 'Verify', detail: 'adversarial refutation per claim' },
    { title: 'Estate join', detail: 'cross-reference against lake/polylogue/lynchpin evidence' },
    { title: 'Synthesize', detail: 'completeness-critiqued synthesis + html-report' },
  ],
}

const SEARCH_STRATEGIES = [
  { key: 'direct', prompt: 'Search directly for the question as asked, using the most natural query phrasing a domain expert would use.' },
  { key: 'adjacent', prompt: 'Search for adjacent/related terminology, synonyms, and the technical vocabulary a specialist would use instead of the question\'s own wording -- find sources that would be missed by a literal search.' },
  { key: 'contrarian', prompt: 'Search specifically for disagreement, criticism, failure cases, and minority positions on this question -- what would someone arguing the OPPOSITE case cite?' },
  { key: 'primary', prompt: 'Search specifically for primary sources: original papers, official documentation, first-party announcements, raw data -- not secondary summaries or blog posts about the topic.' },
  { key: 'recent', prompt: 'Search specifically for the most recent developments, changes, or reversals on this question -- what\'s new in the last few months that older sources wouldn\'t reflect?' },
]

const FETCH_SCHEMA = {
  type: 'object',
  properties: {
    sources: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          url: { type: 'string' },
          title: { type: 'string' },
          searchStrategy: { type: 'string' },
          relevance: { type: 'string', description: 'one sentence: why this source matters to the question' },
        },
        required: ['url', 'title', 'relevance'],
      },
    },
  },
  required: ['sources'],
}

const EXTRACT_SCHEMA = {
  type: 'object',
  properties: {
    claims: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          claim: { type: 'string' },
          sourceUrl: { type: 'string' },
          quote: { type: 'string', description: 'the exact supporting text from the source' },
          confidence: { type: 'string', enum: ['stated-as-fact', 'stated-as-opinion', 'inferred'] },
        },
        required: ['claim', 'sourceUrl', 'quote', 'confidence'],
      },
    },
  },
  required: ['claims'],
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    refuted: { type: 'boolean' },
    reasoning: { type: 'string' },
    counterEvidence: { type: 'string', description: 'empty string if none found' },
  },
  required: ['refuted', 'reasoning'],
}

const CRITIC_SCHEMA = {
  type: 'object',
  properties: {
    uncoveredAngles: {
      type: 'array',
      items: { type: 'string' },
      description: 'specific angles, sub-questions, or source types the research missed -- not generic caveats',
    },
    confidenceAssessment: { type: 'string' },
  },
  required: ['uncoveredAngles', 'confidenceAssessment'],
}

const question = args?.question
if (!question) throw new Error('deep-research requires args.question')
const depthBudget = args?.depthBudget === 'exhaustive' ? 'exhaustive' : 'standard'
const includeEstateEvidence = args?.includeEstateEvidence !== false
const voteCount = depthBudget === 'exhaustive' ? 5 : 3

log(`Deep research on: "${question}" (${depthBudget} budget, ${voteCount}-vote verification)`)

// --- Phase: Search (parallel, distinct strategies) ---
phase('Search')
const searchResults = await parallel(
  SEARCH_STRATEGIES.map((s) => () =>
    agent(
      `Research question: "${question}"\n\n${s.prompt}\n\nReturn every genuinely relevant source you find -- do not cap yourself at a small number, this is an exhaustive pass. For each source give its URL, title, which search strategy found it (use "${s.key}"), and one sentence on its relevance.`,
      { label: `search:${s.key}`, phase: 'Search', schema: FETCH_SCHEMA }
    )
  )
)

// Dedup by URL across all strategies -- genuinely needs the full set at
// once, a barrier is correct here.
const seen = new Set()
const sources = []
for (const r of searchResults.filter(Boolean)) {
  for (const s of r.sources || []) {
    if (!seen.has(s.url)) {
      seen.add(s.url)
      sources.push(s)
    }
  }
}
log(`${sources.length} unique sources found across ${SEARCH_STRATEGIES.length} search strategies`)

let result
if (sources.length === 0) {
  result = { question, error: 'no sources found', sources: [], claims: [], confirmedClaims: [] }
} else {
  // --- Phase: Fetch + Extract, pipelined per source (no barrier -- source A
  // can be verifying while source B is still being fetched) ---
  const fetchExtractVerify = await pipeline(
    sources,
    // Fetch full text and extract claims in one agent call per source --
    // splitting fetch/extract into separate stages would double the
    // dispatch count for no benefit, since extraction needs the fetched
    // text immediately and nothing else consumes the raw fetch.
    (source) =>
      agent(
        `Fetch the FULL TEXT of this source (not a summary, not a snippet -- the whole page/document) and extract every factual claim relevant to the research question below. For each claim, quote the exact supporting text and mark whether it's stated as fact, stated as opinion, or your own inference from the text.\n\nSource: ${source.url} ("${source.title}")\nResearch question: "${question}"`,
        { label: `fetch+extract:${source.url}`, phase: 'Fetch', schema: EXTRACT_SCHEMA }
      ),
    // Verify each extracted claim adversarially, N-vote majority (no
    // single-verifier false confidence).
    async (extraction, source) => {
      if (!extraction?.claims?.length) return { source, claims: [] }
      const verified = await parallel(
        extraction.claims.map((c) => () =>
          parallel(
            Array.from({ length: voteCount }, () => () =>
              agent(
                `Try to REFUTE this claim. Default to refuted=true if you cannot find clear support or find any contradicting evidence. Be skeptical, not agreeable.\n\nClaim: "${c.claim}"\nSupporting quote from source: "${c.quote}"\nSource: ${source.url}`,
                { label: `verify:${c.claim.slice(0, 40)}`, phase: 'Verify', schema: VERDICT_SCHEMA }
              )
            )
          ).then((votes) => {
            const valid = votes.filter(Boolean)
            const refuteCount = valid.filter((v) => v.refuted).length
            return {
              ...c,
              sourceUrl: source.url,
              sourceTitle: source.title,
              survivesVerification: valid.length > 0 && refuteCount < Math.ceil(valid.length / 2),
              refuteVotes: refuteCount,
              totalVotes: valid.length,
            }
          })
        )
      )
      return { source, claims: verified }
    }
  )

  const allClaims = fetchExtractVerify.filter(Boolean).flatMap((r) => r.claims || [])
  const confirmedClaims = allClaims.filter((c) => c.survivesVerification)
  log(`${allClaims.length} claims extracted, ${confirmedClaims.length} survived adversarial verification`)

  // --- Phase: Estate evidence join (optional, this repo's actual delta
  // over the studied reference implementations) ---
  phase('Estate join')
  let estateEvidence = null
  if (includeEstateEvidence) {
    estateEvidence = await agent(
      `Research question: "${question}"\n\nSearch this operator's own evidence planes for anything relevant: Polylogue (past AI-session history -- "have I researched this before, what did I conclude"), Lynchpin (personal analysis products), and the sinnix capture lake (captured browsing/documents that might already contain relevant material). Report what you find, or explicitly state nothing relevant exists in any of the three planes -- do not guess.`,
      { label: 'estate-evidence-join', phase: 'Estate join' }
    )
  }

  // --- Phase: Synthesize + completeness critic ---
  phase('Synthesize')
  const claimSummary = confirmedClaims
    .map((c) => `- ${c.claim} [${c.sourceTitle}](${c.sourceUrl})`)
    .join('\n')
  const critique = await agent(
    `Research question: "${question}"\n\nConfirmed claims found so far:\n${claimSummary}\n\nWhat specific angles, sub-questions, source types, or perspectives does this research miss? Not generic caveats ("more research needed") -- name the SPECIFIC uncovered angle, e.g. "no source from outside the English-language literature" or "nothing on the 2024 counter-argument from X". Also give an honest confidence assessment of what's confirmed.`,
    { label: 'completeness-critic', phase: 'Synthesize', schema: CRITIC_SCHEMA }
  )

  const synthesis = await agent(
    `Write the final research synthesis for: "${question}"\n\nConfirmed claims (survived adversarial verification):\n${claimSummary}\n\nRejected/unconfirmed claims (found but did not survive verification -- mention only if relevant to explain what's uncertain):\n${allClaims.filter((c) => !c.survivesVerification).map((c) => `- ${c.claim} [${c.sourceTitle}]`).join('\n') || '(none)'}\n\nEstate evidence found: ${estateEvidence || '(not checked)'}\n\nCompleteness critic's uncovered angles (name these explicitly in the synthesis, don't hide the gaps): ${(critique?.uncoveredAngles || []).join('; ')}\n\nWrite a clear, well-organized synthesis with inline citations. Load and follow the html-report skill's standards, then produce a self-contained HTML report file. Write it to /realm/data/derived/reports/deep-research-<slug>-<date>.html.`,
    { label: 'synthesis+report', phase: 'Synthesize' }
  )

  result = {
    question,
    depthBudget,
    sourceCount: sources.length,
    claimCount: allClaims.length,
    confirmedClaimCount: confirmedClaims.length,
    uncoveredAngles: critique?.uncoveredAngles || [],
    confidenceAssessment: critique?.confidenceAssessment,
    synthesis,
  }
}

return result
