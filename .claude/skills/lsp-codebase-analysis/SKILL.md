---
name: lsp-codebase-analysis
description: |
  Use this skill for semantic code analysis with LSP tools (cclsp MCP).
  Triggers: "find references", "find definition", "rename symbol",
  "type hierarchy", "all implementations", "refactor safely",
  understanding trait/interface usage, tracing call hierarchies.
---

# LSP-Based Code Analysis

Use cclsp (MCP-based LSP) for semantic code understanding. More reliable than grep for tracing types, finding implementations, and refactoring safely.

## Quick Setup

Requires `.mcp.json` in project root:
```json
{"mcpServers": {"cclsp": {"command": "mcp-cclsp", "args": []}}}
```

## Available Tools

| Tool | Purpose |
|------|---------|
| `find_definition` | Where is this symbol defined? |
| `find_references` | All usages across workspace |
| `get_diagnostics` | Compiler errors/warnings for file |
| `rename_symbol` | Safe rename (use `dry_run: true` first) |
| `restart_server` | Reset if results seem stale |

## symbol_kind Mapping

| Language Concept | LSP Kind |
|------------------|----------|
| Rust trait | `interface` |
| Rust struct | `struct` |
| Rust enum | `enum` |
| Function | `function` |
| Method (impl) | `method` |

## When to Use LSP vs Text Search

| LSP (cclsp) | Text Search (grep/rg) |
|-------------|----------------------|
| Type/trait usage across modules | String literals, comments |
| All trait implementations | Config patterns, env vars |
| Call hierarchy tracing | Quick keyword lookup |
| Refactoring impact analysis | Documentation search |
| Dead code detection | Magic strings |

## Analysis Patterns

### Type Lifecycle Tracing
```
1. find_definition → where defined?
2. find_references (constructor) → where created?
3. find_references (type) → where used?
4. find_references (key methods) → what operations?
```

### Trait Implementation Discovery (Rust)
```
1. find_definition on trait
2. find_references (kind: interface) → all impl sites
```

### Safe Refactoring
```
1. find_references → scope of change
2. get_diagnostics → baseline state
3. Make edits
4. get_diagnostics → verify no regressions
```

## rust-analyzer SSR (Rust-specific)

For pattern-based transformations:

```bash
# Search for pattern
rust-analyzer search '$expr.unwrap()'

# Search and replace (suppress cyclic dep warnings)
RA_LOG=error rust-analyzer ssr '$x.unwrap() ==>> $x?'
```

Placeholder syntax:
- `$name` - any AST node
- `${name:kind(literal)}` - constrained match

## Supported Languages

| Extension | Server |
|-----------|--------|
| `.rs` | rust-analyzer |
| `.py` | pylsp |
| `.ts/.tsx/.js/.jsx` | typescript-language-server |
| `.go` | gopls |
| `.nix` | nil |

## Best Practices

1. **Start with LSP** for structural understanding, fall back to grep for strings
2. **Check scope first** - find_references before large changes
3. **Restart if stale** - after major changes or branch switches
4. **Combine tools** - LSP for precision, grep for breadth
5. **Verify changes** - get_diagnostics after any refactor

## Common Pitfalls

- Wrong `symbol_kind` (Rust `trait` is `interface`)
- Stale LSP state after switching branches
- Feature-gated code may not be visible
- Macro-generated code partially visible

## Full Documentation

See: `/realm/project/sinnix/dots/ai/instructions/lsp-tooling.md`
