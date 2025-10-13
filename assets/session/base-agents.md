# Session Base Guidance
You are working inside a VS Code driven session workspace. Treat this directory as the canonical root for the idea you are pursuing.

- `SESSION_ROOT` points to the session directory (same place as this file).
- `SESSION_SLUG` is a stable identifier for notes, logging, and Hyprland workspace naming.
- `SESSION_WORK` points to the primary project directory via the `work` symlink. Run builds/tests there.
- Terminal tasks launch from `SESSION_ROOT` but `cd` into `SESSION_WORK` when it is available.
- Keep `scratch.md` current with intent, next steps, and blockers so future helpers can reconnect quickly.
- Use `links/` for extra relevant directories (docs, sandboxes). Mention new links in `scratch.md` for discoverability.
- Do not commit artifacts from `/realm/session`; copy deliverables back into the real project repo before publishing.

Always leave the session ready for handoff: enumerate pending actions, important file paths, and experiment results in `scratch.md` or dedicated notes.
