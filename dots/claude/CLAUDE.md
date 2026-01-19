# Task and Time Tracking Protocol (Agent)

**ALWAYS ACTIVE**: Use taskwarrior and timewarrior to track work during conversations in this project.

## Critical Rules

1. **Identity**
   ```bash
   # Set agent identity once per environment.
   export AGENT_NAME="codex"  # or claude, gemini, etc.
   export AGENT_SESSION_ID="${AGENT_SESSION_ID:-${AGENT_NAME}-$(date +%H%M%S)-$$}"
   ```

2. **Separation of Concerns**
   - All agent tasks must have the `+agent` tag.
   - All agent tasks must use `project:agent.*`.
   - User tasks are anything without the `+agent` tag.

3. **Project Namespacing**
   ```
   agent.${AGENT_NAME}.${AGENT_SESSION_ID}   <- This session's work
   agent.shared.${topic}                     <- Shared across sessions
   {anything-else}                           <- User tasks (read-only)
   ```

4. **Ownership Verification**
   ```bash
   # Before modifying ANY task, verify ownership:
   if task {id} export | jq -r '.[0].project // ""' | grep -q '^agent\.'; then
       # Safe - agent task
   else
       # STOP - user task, ask permission
   fi
   ```

## Environment Changes

- **Never** use `nix profile install/add/remove` (or other ad-hoc profile commands) to add tools for the user. All package changes must go through this repo's Nix/NixOS/Home-Manager modules so they are declarative and reproducible.
- If you believe a temporary binary is required, ask the user first or create a derivation/shell via the repo.
- When debugging, prefer disposable shells (`nix develop`, `nix shell`, etc.) instead of mutating the user's profiles.

## When to Track

**Create tasks for:**
- User requests (`+user_request`)
- Multi-step work (>3 tool calls or >5 minutes)
- Research and investigation (`+research`)
- Follow-up items (`+follow_up`)

**Track time on:**
- All significant work (>2 minutes)
- Use tags: `agent`, `agent_${AGENT_NAME}`, `session_${AGENT_SESSION_ID}`, `{activity}` (timewarrior uses tags only)

## Core Commands

**Using helpers** (recommended):
```bash
source /realm/project/sinnix/dots/taskwarrior/agent-helpers.sh

# Track user request
agent_track_request "Description" "30min" "H"

# Annotate current work
agent_annotate "Finding or note"

# Complete task
agent_complete_task {id} "actual-time"

# Show status
agent_status

# Session summary
agent_session_summary
```

**Direct usage**:
```bash
task add "User request: {desc}" \
    project:agent.$AGENT_NAME.$AGENT_SESSION_ID \
    priority:H \
    tags:agent,user_request \
    estimate:30min

timew start agent agent_${AGENT_NAME} session_${AGENT_SESSION_ID} conversation

task {id} modify actual:45min
task {id} done
timew stop
```

## Read-Only User Task Interaction

**CAN do:**
```bash
task -agent status:pending
```

**CANNOT do:**
- Modify user's tasks without explicit permission
- Delete user's tasks
- Add `+agent` to user's tasks
- Track time on user's tasks (unless asked)

## Multi-Session Coordination

**Check for others at startup:**
```bash
OTHERS=$(task +ACTIVE +agent project.startswith:agent.$AGENT_NAME. count)
if [ "$OTHERS" -gt 0 ]; then
    echo "WARNING: $OTHERS other session(s) active"
fi
```

**View separation:**
```bash
task project:agent.$AGENT_NAME.$AGENT_SESSION_ID
task +ACTIVE +agent project.startswith:agent.$AGENT_NAME.
task +agent
task -agent
```

## Proactive Behavior

**MUST track when:**
1. User makes explicit request
2. Starting significant work (>2 min)
3. Discovering issues or findings
4. Creating follow-up items

**Report when:**
- User asks "what have we done?"
- Natural break points in conversation
- Completing major work

## File Locations

- Helpers: `/realm/project/sinnix/dots/taskwarrior/agent-helpers.sh`
- Detailed skill: `/realm/project/sinnix/.claude/skills/task-tracking.md`
- User guide: `/realm/project/sinnix/dots/README-agent-task-tracking.md`
- Multi-session FAQ: `/realm/project/sinnix/dots/README-agent-multi-instance-faq.md`

## Success Criteria

- Every significant user request is tracked
- All agent tasks have `+agent` and `project:agent.*`
- Session IDs prevent conflicts
- User's tasks remain untouched
- Time tracking provides insights

---

# Rust Tooling

## rust-analyzer SSR (Structural Search Replace)

For semantic refactoring across a Rust codebase, use `rust-analyzer ssr`:

```bash
rust-analyzer ssr '<pattern> ==>> <replacement>'
```

**Syntax:**
- `$name` - placeholder matching any AST node (expr, type, path, pattern, item)
- `==>>` - separates search pattern from replacement
- Paths resolve contextually (e.g., `Bar` in module `foo` matches `foo::Bar` elsewhere)

**Examples:**
```bash
# Rename method calls
rust-analyzer ssr '$ctx.with_shared_nats() ==>> $ctx.with_nats().shared()'

# Convert function to method (UFCS)
rust-analyzer ssr 'foo($a, $b) ==>> $a.foo($b)'

# With constraints: ${name:constraint}
rust-analyzer ssr '${x:kind(literal)}.to_string() ==>> format!("{}", $x)'
```

**Constraints:** `kind(literal)`, `not(a)`, etc.

**Scope:** Applies to current selection if any, otherwise whole workspace.

**Search only:** Use `rust-analyzer search '$pattern'` to find matches without replacing.

## cclsp (LSP via MCP)

Config: `~/.config/claude/cclsp.json` (symlinked from sinnix)
Enable per-project via `.mcp.json`:
```json
{"mcpServers": {"cclsp": {"command": "mcp-cclsp", "args": []}}}
```

**Tools:** `find_definition`, `find_references`, `rename_symbol`, `get_diagnostics`

## Refactoring Workflow

cclsp and rust-analyzer CLI are complementary:

| Task | Tool |
|------|------|
| Understand scope | `cclsp:find_references` |
| Batch transform | `rust-analyzer ssr` |
| Verify no breakage | `cclsp:get_diagnostics` |

**Example workflow:**
```bash
# 1. Check references first (via cclsp MCP)
# 2. Apply SSR
rust-analyzer ssr '$ctx.with_shared_nats() ==>> $ctx.with_nats().shared()'
# 3. Verify diagnostics (via cclsp MCP)
```

---

# Context7 (Documentation Lookup)

**Use liberally** for library/framework questions. Faster and more accurate than guessing or web search.

```
1. resolve-library-id  → get Context7 library ID
2. query-docs          → fetch relevant docs/examples
```

**When to use:**
- Unfamiliar library APIs
- Checking current best practices
- Verifying syntax before writing code
- Understanding framework conventions

Don't hesitate—context7 queries are cheap and prevent mistakes.
