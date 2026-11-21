---
name: plannotator-inbox
description: Use the private review Inbox for decisions, visual comparisons, important changes, completed reports, guided code reviews, and replies across continuing work.
---

# Plannotator Inbox

Use the existing thread for the project and work stream. List threads first. On resumption read the latest reply, apply the operator’s choices and explain the change there. A worker reports to its coordinating agent, which owns the operator conversation.

For a decision, give enough context to understand what would change. Compare viable alternatives with current behavior, show an example when the difference is experiential, and say which you recommend and why. Put a single coherent decision in a `:::question` block with selectable options, or use `:::question-text` for an open design question. Use an annotated screenshot, short motion study or interactive HTML comparison when it helps the operator discover a preference. Readers can answer later. Continue work that does not depend on their choice.

Post an important change when it affects the operator’s decision or expectations. Deliver a short outcome and the actual file for completed work; link the attachment by basename in the body. For a guided code review use `get_guide_brief` and submit the guide with its exact patch. Keep tasks in their owning tracker. Respect a request to keep a draft or question in chat.

## Clients

- Claude Code uses the native Plannotator Inbox tool. Codex CLI uses the `plannotator-inbox` MCP tools. Use the project of the work; when passing a project explicitly, use its absolute directory. Preserve the returned thread link.
- In ChatGPT use the Sinnix Agent Gateway. Discover `plannotator-inbox` with `mcp.tools`, read with `mcp.call`, and send with `mcp.change` and an idempotency key. Use the same absolute project path and conversation identifier on subsequent calls. Attach files already on the workstation. A ChatGPT-generated file must reach the workstation before it can be attached.
- The send receipt states whether the client receives replies automatically. When it cannot, read the named thread on resumption or the next relevant turn. A pending Inbox decision stays in its thread.
- Run `plannotator inbox --open` when asked to open the window. Tool sends can start the Inbox themselves. The installed `plannotator inbox --help` describes question syntax, attachment handling and client reply delivery.
