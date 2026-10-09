---
name: chatgpt-conversations
description: Read complete ChatGPT conversations and inspect or explicitly download generated files from already open Chrome tabs, without navigating or submitting messages.
---

# ChatGPT conversations

Use this skill for the operator's currently open ChatGPT conversations. Full
reads use the provider-native conversation endpoint in an explicitly selected
tab. Use Polylogue for durable historical session search.

Run the bundled `scripts/sinnix-chatgpt-conversations` helper. It uses the
shared Chrome CDP control plane and requires an explicit page ID for reads
and downloads. Read commands do not alter the browser.

## Read conversations

1. Start with `scripts/sinnix-chatgpt-conversations list`. It returns one
   compact row per open ChatGPT conversation with rendered-DOM counts plus
   cheap native evidence (`native_status`, mapping count, and native message
   count).
2. When the work requires the actual conversation, use the provider-native
   active branch and complete text:

   ```bash
   scripts/sinnix-chatgpt-conversations full <page-id>
   ```

   The result is ordered from root to `current_node`, includes stable provider
   IDs, roles, timestamps, attachment metadata, fidelity and provenance, and
   retains complete native records in `all_messages` plus an `all_mapping_nodes`
   index for every branch. Use
   `--output FILE` for a large record; it is created atomically with mode 600.
   Native failure is explicitly marked `fidelity: dom_degraded` and
   `provenance.complete: false`.

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

The helper returns `sinnix-chatgpt-conversation-v2` records for `full`. Each
native message has:

- root-to-current-branch order, `provider_id`, `node_id`, parent ID, role,
  complete text, ISO timestamp, and provider attachment metadata;
- `provenance.source: chatgpt_backend_api`, `fidelity: native`, and
  `provenance.complete: true`.

`read` remains the bounded rendered-DOM route and returns v1 records with
explicit text paging. Its counts describe rendered content only; it is not a
complete-conversation proof.

An attachment reference proves that the tab visibly rendered it and gives the
agent stable page, message, and attachment context for a requested action. It
does not itself provide a local file path. Generated assistant files can be
preview controls absent from native `metadata.attachments`. Inspect their
rendered inventory without opening them:

```bash
scripts/sinnix-chatgpt-conversations artifacts <page-id>
```

When the operator explicitly requests a generated file, download it from the
selected tab and verify the returned path, byte count, and SHA-256:

```bash
scripts/sinnix-chatgpt-conversations download <page-id> <generated-filename>
```

This opens and closes the file viewer in that tab but does not navigate or
submit. It uses the configured Downloads directory and accepts only a new file with
the exact name or Chrome's numbered collision name. Multiple matching files
are ambiguous and fail; filenames alone cannot distinguish a simultaneous
download of the same name. For repeated names, select one with `--occurrence N`,
using its zero-based position among matching controls from `artifacts`.
Generated-file inventory describes rendered controls, not unseen branches.
Sandbox-file links in old assistant turns are frequently
expired on ChatGPT's side; a null `href` plus a button control is normal.

Before considering a download of an uploaded file, run
`scripts/sinnix-chatgpt-conversations locate "<attachment label>"`. Uploaded
files always originated on this machine and generated bundles are often
already downloaded, so the file is usually findable locally — the command
strips kind words from the label, tries the exact name, collision-suffix
variants (" (1)" added or removed), and a de-parenthesized core substring
across the inbox, scratch, exports, trash, and home roots (extendable with
`--root`). Trash hits include the `.trashinfo` sidecar, which records the
original path.

Canvas documents ("writing blocks") are captured completely: a canvas body is
part of the containing turn's `text` exactly as rendered, and each turn also
carries a `canvases` array identifying every canvas — `block_id`, `title`
(its leading heading), `text_characters`, and `text_offset` locating the body
inside the turn text. Slice the turn text at `text_offset` for that many
characters to recover the canvas document alone.

## Boundaries

- Never infer an unseen conversation from tab titles or summaries. Read the
  relevant turn range.
- Do not treat a ChatGPT answer as verified system state. Check the owning
  codebase, Beads, runtime, or source before acting on a factual claim.
- Do not commit transcript content or create an automatic archive. Retrieve the
  complete native conversation when requested, and persist or download only
  when the operator asks for that result.
- This skill is for `chatgpt.com/c/...` tabs already open in the browser. It
  does not authenticate, open new chats, or search the user’s account.
