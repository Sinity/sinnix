# LSP-Based Code Analysis (All Agents)

Use LSP tools for semantic code understanding. Available via MCP when `.mcp.json` is present.

## Setup

Every project needs `.mcp.json` in its root:
```json
{"mcpServers": {"cclsp": {"command": "mcp-cclsp", "args": []}}}
```

Template: `/realm/project/sinnix/dots/claude/mcp-template.json`

Global LSP config: `~/.config/claude/cclsp.json` (symlinked from sinnix)

## MCP Tools Available

### find_definition
Find where a symbol is defined.
```
file_path: /path/to/file.ext
symbol_name: SymbolName
symbol_kind: struct|function|method|enum|interface|class|variable
```

### find_references
Find all usages of a symbol across workspace.
```
file_path: /path/to/file.ext
symbol_name: method_name
symbol_kind: method
include_declaration: true
```

### get_diagnostics
Get compiler errors/warnings for a file.
```
file_path: /path/to/file.ext
```

### rename_symbol
Rename across codebase (use `dry_run: true` to preview).
```
file_path: /path/to/file.ext
symbol_name: old_name
new_name: new_name
dry_run: true
```

### restart_server
Reset LSP state if results seem stale.
```
extensions: ["rs"]  # Optional, restart all if omitted
```

## symbol_kind Reference

| Language Concept | LSP Kind |
|------------------|----------|
| Rust trait | `interface` |
| Rust struct | `struct` |
| Rust enum | `enum` |
| Function | `function` |
| Method (impl) | `method` |
| Class (OOP langs) | `class` |
| Variable/const | `variable` / `constant` |

## When to Use LSP vs Text Search

| LSP (cclsp) | Text Search (grep/rg) |
|-------------|----------------------|
| Type/trait usage across modules | String literals, comments |
| All trait implementations | Config patterns, env vars |
| Call hierarchy tracing | Quick keyword lookup |
| Refactoring impact analysis | Documentation search |
| Dead code detection | Magic strings |

## Analysis Patterns

### Type Lifecycle
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

### Refactoring Safety
```
1. find_references → scope of change
2. get_diagnostics → baseline state
3. Make edits
4. get_diagnostics → verify no regressions
```

### Dead Code Check
```
1. find_references on pub symbol
2. If only 1 reference (definition itself) → likely dead
3. Verify with get_diagnostics (may show warnings)
```

## rust-analyzer CLI (Rust-specific)

Beyond MCP, use CLI for pattern-based operations:

```bash
# Search for pattern
rust-analyzer search '$expr.unwrap()'

# Search and replace
RA_LOG=error rust-analyzer ssr '$x.unwrap() ==>> $x?'
```

Placeholder syntax:
- `$name` - any AST node
- `${name:kind(literal)}` - constrained match

## Supported Languages

Same MCP tools work for all configured LSPs:

| Extension | Server |
|-----------|--------|
| `.rs` | rust-analyzer |
| `.py` | pylsp |
| `.ts/.tsx/.js/.jsx` | typescript-language-server |
| `.go` | gopls |
| `.nix` | nil |
| `.sh/.bash` | bash-language-server |
| `.lua` | lua-language-server |
| `.yml/.yaml` | yaml-language-server |
| `.md` | marksman |

## Best Practices

1. **Start with LSP** for structural understanding, fall back to grep for string patterns
2. **Check scope first** - use find_references before large changes
3. **Restart if stale** - LSP state can lag after major changes
4. **Combine tools** - LSP for precision, grep for breadth
5. **Verify changes** - get_diagnostics after any refactor

## Common Pitfalls

- Wrong `symbol_kind` (Rust `trait` → `interface`)
- Stale LSP state after switching branches
- Feature-gated code may not be visible
- Macro-generated code partially visible
- Workspace scope limits what LSP sees
