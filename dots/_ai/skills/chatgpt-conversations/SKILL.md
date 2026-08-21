---
name: chatgpt-conversations
description: Read complete, structured ChatGPT conversations already open in the operator's Chrome. Use when the user asks to inspect, summarize, continue work from, compare, or act on currently open ChatGPT chats or tabs. Supports full transcripts and optional bounded reads, and never navigates, activates, submits, edits, or closes a tab.
---

# ChatGPT conversations

Use this skill for the operator's currently open ChatGPT conversations. It is a
browser DOM adapter whose truth is the full content currently rendered in an
explicitly selected tab. Use Polylogue for durable historical session search.

Run the bundled `scripts/sinnix-chatgpt-conversations` helper. It uses the
shared Chrome CDP control plane, requires an explicit page ID for individual
reads, and does not alter the browser.

## Read conversations

1. Start with `scripts/sinnix-chatgpt-conversations list`. It returns one
   compact row per open ChatGPT conversation: page ID, URL, title, role order,
   per-turn character counts, attachment-turn indexes, and total characters.
2. When the work requires the actual conversation, read all currently rendered
   turns and their complete text directly:

   ```bash
   scripts/sinnix-chatgpt-conversations full <page-id>
   ```

   Use `--markdown` only when a human-readable handoff is preferable to the
   structured JSON record. Full reads are the normal choice when the agent must
   understand the conversation as a whole.
3. Use `read` only to reduce context usage when a narrower range answers the
   task:

   ```bash
   scripts/sinnix-chatgpt-conversations read <page-id> \
     --message-start 2 --message-limit 2 --text-limit 1600
   ```

   Long turns are explicitly paged. A response contains `text_characters`,
   `text_offset`, `text`, and `text_truncated`. Continue a needed turn without
   replaying its prefix:

   ```bash
   scripts/sinnix-chatgpt-conversations read <page-id> \
     --message-start 3 --message-limit 1 --text-start 1600 --text-limit 2400
   ```

4. `read-open` reads a bounded window from every currently open ChatGPT tab.
   It is useful for triage, while `full <page-id>` is the complete-chat route.

## Transcript contract

The helper returns `sinnix-chatgpt-conversation-v1` records. Each message has:

- stable tab-local `index` and page-provided `message_id` where available;
- `role` and original `text_characters`;
- complete text from `full`, or a paged `text` segment with an explicit
  truncation flag from `read`;
- rendered `links`; and
- visible attachment references, including their turn-local `index`, label,
  kind, test ID, direct href when ChatGPT exposes one, and rendered control
  metadata.

An attachment reference proves that the tab visibly rendered it and gives the
agent stable page, message, and attachment context for a requested action. It
does not itself provide a local file path. Downloading, opening, uploading,
navigating, submitting, and other browser mutations require an explicit
operator request and a verified result.

## Boundaries

- Never infer an unseen conversation from tab titles or summaries. Read the
  relevant turn range.
- Do not treat a ChatGPT answer as verified system state. Check the owning
  codebase, Beads, runtime, or source before acting on a factual claim.
- Do not commit transcript content or create an automatic archive. Retrieve the
  complete rendered conversation when requested, and persist or download only
  when the operator asks for that result.
- This skill is for `chatgpt.com/c/...` tabs already open in the browser. It
  does not authenticate, open new chats, or search the user’s account.

## Routing validation

Before this skill, generic browser control could evaluate a page but did not
provide an ordered conversation schema, turn paging, or attachment extraction.
The forward probe used the request “read the currently open ChatGPT chats and
act on the relevant messages”: the helper enumerated five open conversation
tabs, extracted their role/count summaries, and paged a selected assistant
turn with its visible attachment labels. The non-trigger “open a new ChatGPT
chat and submit this prompt” remains browser-action work and does not select
this read-only transcript skill.
