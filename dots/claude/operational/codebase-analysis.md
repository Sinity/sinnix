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
