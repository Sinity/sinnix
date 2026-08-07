# Publication egress guard

Claude Code's Bash `PreToolUse` hook invokes `sinnix-egress-scan` for explicit `gh api` mutations and `gh pr create`. It scans only content-bearing fields and files up to 1 MiB. A match denies the publication without printing matched bytes. An override is available through `SINNIX_EGRESS_GUARD_OVERRIDE=1`; it records an event and reason without the payload.

Supported high-confidence detectors cover OpenAI-style keys, GitHub tokens, AWS access-key IDs, Slack tokens, and PEM private-key headers. Binary files containing NUL bytes are passed to a dedicated binary or image policy rather than decoded as text. Oversized files, unreadable files, stdin input, arbitrary upload commands, and non-public commands are outside this text guard's scope. Git history and screenshots require their owning publication or privacy checks.

The guard is advisory only for content it can resolve. It does not replace credential rotation, repository review, or service-specific artifact privacy checks.
