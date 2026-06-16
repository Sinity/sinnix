## Codebase Analysis Workflow

### Survey → Narrate → Synthesize

For thorough code review or bug hunting, use the `analyze` or `swarm` skill:

1. **Survey** (BFS): List all items at current level (crates/modules/files), note concerns without deep-diving
2. **Narrate** (DFS): For highest-concern item, verbalize line-by-line what each piece does
3. **Synthesize**: Return to broad view, cross-reference findings across related code

### Concrete Bug-Finding Techniques

These actually work (empirically validated on sinex codebase):

- **Line-by-line narration**: Verbalizing forces attention, surfaced 16 bugs in one session
- **Cross-reference related functions**: Comparing `register()` vs `list()` found key format mismatch
- **Check get→modify→put patterns** for race conditions in distributed code

### Analysis Skills

- `analyze <target>` - Interactive analysis with user steering (survey → narrate → synthesize)
- `swarm <target> --preset analyze` - Autonomous parallel analysis

### Semantic MCPs

Serena and `codebase-memory-mcp` are registered for Codex, Claude, Gemini, and
VS Code.

Use Serena first for symbol-level navigation and edits: finding symbols,
references, overviews, and renames/replacements that should respect language
structure. Serena is configured for `sinex`, `polylogue`, `sinity-lynchpin`,
and `sinnix` via `.serena/project.yml`; it activates from the current working
directory in Claude/Codex/Gemini. If needed, ask the agent to activate the
current project with Serena and read its initial instructions.

Use Codebase Memory for graph-wide architecture, impact, dead-code, and
cross-repo structural queries:

```bash
codebase-memory-mcp cli index_repository '{"repo_path": "/realm/project/<repo>"}'
codebase-memory-mcp cli get_architecture '{"project": "<repo>"}'
codebase-memory-mcp cli search_graph '{"name_pattern": ".*Handler.*"}'
codebase-memory-mcp cli detect_changes '{"repo_path": "/realm/project/<repo>"}'
```

Indexes live under `~/.local/share/codebase-memory-mcp` so they survive
impermanence boots. Serena global state lives under `~/.local/share/serena`
and its uv tool installation under `~/.local/state/serena`. Keep using `rg` for
precise literal text search and for files that are not yet indexed.
