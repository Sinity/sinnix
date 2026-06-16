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

Use them deliberately; they overlap, but they are not interchangeable.

Default sequence for code exploration:

1. Use `rg` for exact literal text and for unindexed/generated surfaces.
2. Use Codebase Memory `search_code` for broad "where does this concept show
   up?" queries. It is fast, persistent across sessions, and returns containing
   functions/modules with context and graph metadata.
3. Use Serena when you are near an edit boundary: file symbol overviews,
   precise symbol lookup, references grouped by containing symbol, diagnostics,
   rename, safe-delete, and symbol-body replacement.

Serena is the language-aware editing tool. Prefer it for symbol-level navigation
and edits that should respect Rust/Python/Nix structure. It is configured for
`sinex`, `polylogue`, `sinity-lynchpin`, and `sinnix` via `.serena/project.yml`;
it activates from the current working directory in Claude/Codex/Gemini. If
Serena tools are missing in Codex even though `get_current_config` says they are
active, use tool discovery for the exact operation name (`find_symbol`,
`find_referencing_symbols`, `get_symbols_overview`, etc.); Codex lazy loading can
hide active Serena tools until searched. If needed, activate the current project
with Serena and read its initial instructions.

Codebase Memory is the indexed graph/search substrate. The strongest day-to-day
tool is `search_code`: graph-enriched grep that deduplicates raw matches into
containing symbols and ranks definitions/important functions ahead of tests.
Use `get_code_snippet` after `search_graph`/`search_code` gives an exact
qualified name. Treat `get_architecture`, semantic vector search, `trace_path`,
`detect_changes`, and custom Cypher as exploratory hints until validated against
source/Serena; on Rust repos these can be noisy or incomplete, especially for
call edges and change-impact claims. Re-index before relying on change or impact
answers.

```bash
codebase-memory-mcp cli index_repository '{"repo_path": "/realm/project/<repo>"}'
codebase-memory-mcp cli get_architecture '{"project": "<repo>"}'
codebase-memory-mcp cli search_code '{"project": "realm-project-<repo>", "pattern": "MaterialReadySet"}'
codebase-memory-mcp cli search_graph '{"project": "realm-project-<repo>", "query": "event persistence"}'
```

Indexes live under `~/.local/share/codebase-memory-mcp` so they survive
impermanence boots. Serena global state lives under `~/.local/share/serena`
and its uv tool installation under `~/.local/state/serena`. Keep using `rg` for
precise literal text search and for files that are not yet indexed.
