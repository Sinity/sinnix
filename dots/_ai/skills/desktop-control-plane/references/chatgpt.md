# ChatGPT browser work

Use the shared Chrome CLI on explicit page IDs. Create new work with
`agent-window`; inspect an existing chat only when the operator selected it or
you created it. User requests to ask another model authorize submitting that
task and its relevant supplied references, not unrelated account data.

## Prepare and submit

1. Save the prompt as UTF-8 text. For several chats, give each a distinct
   question and output contract; include source links and executor limits.
2. Inspect `page-snapshot` for the composer and model picker. Select the
   requested model and effort through the current UI. Record the visible
   selected label; do not infer an exact backend from a generic Pro label.
3. Insert the entire prompt in one operation:

   ```bash
   sinnix-chrome-control inject-text <page-id> \
     --selector '[role="textbox"][contenteditable="true"]' \
     --text-file /path/to/prompt.txt
   ```

   `inject-text` inserts at the field's selection; it does not replace an
   existing draft. For replacement, select only the intended composer's text
   first. Use `key` for keyboard shortcuts, not one command per character.
   `fill-form` targets input values, not rich contenteditable composers.

4. Read back the composer and compare its complete text with the prompt,
   allowing rendered whitespace differences. Preserve mention chips and
   attachments. Add app mentions such as Deep Research after inserting the
   body if replacing text would remove the chip.
5. Use `upload-files` against the inspected file input. Check accepted types,
   attachment names, upload errors and progress controls. React may clear the
   file input after accepting files, so the helper's `attached: 0` alone does
   not prove failure. Verify the rendered attachments and enabled send button.
6. Submit once. Check for the user message, conversation URL, and a response
   or active generation control. If the outcome is uncertain, inspect that
   chat before retrying; do not duplicate a submission.

DOM actions are preferable to coordinates for hidden or changing layouts.
When `click` cannot reach a rendered control reliably, `evaluate` can call
`click()` on the exact inspected DOM element. Inspect the resulting UI before
the next adaptive action. Browser evaluation is for visible UI and documented
read capabilities, not hidden application state or inferred write endpoints.

## Research apps and results

An outer chat saying it opened Deep Research is not proof that research is
running. Inspect the app's plan and actual state; proceed through a plan-start
control when present and within the requested research scope.

For nested apps, inspect the parent page's iframe title and URL. Match that URL
to an iframe target from `list --json`; evaluate only that target. A wrapper
may contain a same-origin inner iframe whose `contentDocument` holds the UI.
Read its rendered text and controls, then act on those inspected controls.
Do not navigate the wrapper away from its initialization URL.

For complete outputs and generated-file inventory, load
[chatgpt-conversations](../../chatgpt-conversations/SKILL.md) and use its
bundled helper with the exact page ID. DOM tails can establish progress, but
cannot establish complete output. Check cited evidence before presenting
another model's answer as a verified fact. Record chat URLs and remaining work
when handing off; schedule monitoring only when requested.
