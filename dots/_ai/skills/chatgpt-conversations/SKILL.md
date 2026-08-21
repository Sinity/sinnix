---
name: chatgpt-conversations
description: Read structured, token-efficient transcripts from ChatGPT conversations already open in the operator's Chrome. Use when the user asks to inspect, summarize, continue work from, compare, or act on currently open ChatGPT chats or tabs. This skill reads only explicit ChatGPT tab IDs and never navigates, activates, submits, edits, or closes a tab.
---

# ChatGPT conversations

Use this skill for the operator's currently open ChatGPT conversations. It is a
browser DOM adapter, not an archive: its truth is what the loaded tab currently
renders. Use Polylogue for durable historical session search instead.

Run the bundled `scripts/sinnix-chatgpt-conversations` helper. It uses the
shared Chrome CDP control plane, requires an explicit page ID for individual
reads, and does not alter the browser.

## Read efficiently

1. Start with `scripts/sinnix-chatgpt-conversations list`. It returns one
   compact row per open ChatGPT conversation: page ID, URL, title, role order,
   per-turn character counts, attachment-turn indexes, and total characters.
2. Pick only the tab and turns needed for the task. Read a bounded turn window:

   ```bash
   scripts/sinnix-chatgpt-conversations read <page-id> \
     --message-start 2 --message-limit 2 --text-limit 1600
   ```

3. Long turns are explicitly paged. A response contains `text_characters`,
   `text_offset`, `text`, and `text_truncated`. Continue a needed turn without
   replaying its prefix:

   ```bash
   scripts/sinnix-chatgpt-conversations read <page-id> \
     --message-start 3 --message-limit 1 --text-start 1600 --text-limit 2400
   ```

4. Use `--text-limit 0` only when the whole selected turn is necessary. Use
   `--markdown` when a human-readable handoff is better than structured JSON.
   `read-open` reads a bounded window from every currently open ChatGPT tab,
   but `list` followed by targeted `read` is the normal low-token route.

## Transcript contract

The helper returns `sinnix-chatgpt-conversation-v1` records. Each message has:

- stable tab-local `index` and page-provided `message_id` where available;
- `role` and original `text_characters`;
- a paged `text` segment and an explicit truncation flag;
- rendered `links`; and
- visible attachment references (`label`, kind, test ID, and href when ChatGPT
  exposes one).

An attachment reference proves only that the tab visibly rendered it. It does
not provide a local file path or authorize a download. Ask the operator before
any download, upload, navigation, submission, or other browser mutation.

## Boundaries

- Never infer an unseen conversation from tab titles or summaries. Read the
  relevant turn range.
- Do not treat a ChatGPT answer as verified system state. Check the owning
  codebase, Beads, runtime, or source before acting on a factual claim.
- Do not create a second archive or commit transcript content. Return bounded
  excerpts, page IDs, message IDs, and links to the agent that needs them.
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
