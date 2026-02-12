# LSP-Based Codebase Analysis

Use cclsp (LSP via MCP) and rust-analyzer CLI for semantic code understanding. These tools provide **compile-time verified** information - more reliable than grep/ripgrep for understanding code structure.

## Quick Setup for New Projects

Copy the MCP config template to enable cclsp:

```bash
cp /realm/project/sinnix/dots/claude/mcp-template.json /path/to/project/.mcp.json
```

Or create manually:

```json
{ "mcpServers": { "cclsp": { "command": "mcp-cclsp", "args": [] } } }
```

The global cclsp config (`~/.config/claude/cclsp.json`) handles language server selection automatically based on file extension.

## When to Use LSP Tools

**Prefer LSP over text search when:**

- Tracing type usage across crate boundaries
- Finding all implementations of a trait
- Understanding call hierarchies
- Verifying refactoring safety
- Finding dead/unreachable code

**Still use grep/rg for:**

- String literals, comments, documentation
- Configuration patterns (env vars, magic strings)
- Quick keyword searches where semantic precision isn't needed

## cclsp Tools Reference

### find_definition

Find where a symbol is defined.

```
file_path: /path/to/file.rs
symbol_name: EventBuilder
symbol_kind: struct  # or: function, method, enum, interface, class
```

**Use for:** Understanding where a type/function comes from, jumping to source.

### find_references

Find all usages of a symbol across the workspace.

```
file_path: /path/to/file.rs  # File where symbol is defined
symbol_name: build
symbol_kind: method
include_declaration: true
```

**Use for:** Impact analysis, understanding coupling, finding callers.

**Valid symbol_kind values:** `file`, `module`, `namespace`, `package`, `class`, `method`, `property`, `field`, `constructor`, `enum`, `interface`, `function`, `variable`, `constant`, `string`, `number`, `boolean`, `array`, `object`, `key`, `null`, `enum_member`, `struct`, `event`, `operator`, `type_parameter`

Note: Rust `trait` maps to `interface` in LSP.

### get_diagnostics

Get compiler errors, warnings, hints for a file.

```
file_path: /path/to/file.rs
```

**Use for:** Verifying code compiles after changes, finding issues before running cargo.

### rename_symbol / rename_symbol_strict

Rename a symbol across the codebase.

```
file_path: /path/to/file.rs
symbol_name: old_name
new_name: new_name
dry_run: true  # Preview changes without applying
```

**Use for:** Safe refactoring with compiler verification.

## rust-analyzer CLI

### Structural Search Replace (SSR)

Semantic pattern matching and replacement:

```bash
# Search only
rust-analyzer search '$pattern'

# Search and replace
rust-analyzer ssr '$pattern ==>> $replacement'

# Suppress noisy warnings
RA_LOG=error rust-analyzer ssr '...'
```

**Placeholder syntax:**

- `$name` - matches any AST node
- `${name:constraint}` - with constraint (e.g., `${x:kind(literal)}`)

**Examples:**

```bash
# Find all unwrap() calls
rust-analyzer search '$expr.unwrap()'

# Convert Result handling pattern
rust-analyzer ssr '$x.map_err(|e| SinexError::from(e))? ==>> $x?'

# Find specific method chains
rust-analyzer search '$ctx.pool().events()'
```

## Analysis Patterns

### 1. Type Lifecycle Tracing

Understand how a type flows through the system:

```
1. find_definition → where is it defined?
2. find_references on constructors → where is it created?
3. find_references on the type itself → where is it used?
4. find_references on key methods → what operations are performed?
```

### 2. Trait Implementation Discovery

Find all implementors of a trait:

```
1. find_definition on trait → get the trait location
2. find_references on trait name (kind: interface) → find impl blocks
3. For each impl, find_references on implemented methods
```

### 3. Call Chain Analysis

Trace execution flow:

```
1. find_references on entry point (e.g., main, handler)
2. For each caller, find_references recursively
3. Build call graph from results
```

### 4. Refactoring Safety Check

Before modifying code:

```
1. find_references → understand all usage sites
2. get_diagnostics on affected files → verify current state
3. Make changes
4. get_diagnostics again → verify no new errors
```

### 5. Dead Code Detection

Find unused symbols:

```
1. find_references on pub functions/types
2. If references == 1 (just the definition), likely dead
3. Verify with get_diagnostics (may show warnings)
```

## Multi-Language Support

cclsp supports multiple languages via `~/.config/claude/cclsp.json`:

| Extension                    | Language Server            |
| ---------------------------- | -------------------------- |
| `.rs`                        | rust-analyzer              |
| `.py`, `.pyi`                | pylsp                      |
| `.ts`, `.tsx`, `.js`, `.jsx` | typescript-language-server |
| `.go`                        | gopls                      |
| `.nix`                       | nil                        |
| `.sh`, `.bash`               | bash-language-server       |
| `.lua`                       | lua-language-server        |
| `.yml`, `.yaml`              | yaml-language-server       |
| `.md`                        | marksman                   |

Same cclsp tools work across all languages.

## Combining Tools

### Thorough Analysis Workflow

```
1. Initial exploration
   - Glob for file patterns
   - find_definition for key types

2. Dependency mapping
   - find_references on core types
   - Build usage graph

3. Pattern discovery
   - rust-analyzer search for code patterns
   - Categorize and count occurrences

4. Verification
   - get_diagnostics on modified files
   - Cross-check with cargo check
```

### Refactoring Workflow

```
1. Scope: find_references → how many files affected?
2. Plan: Can rust-analyzer ssr handle it, or manual?
3. Execute: ssr or manual edits
4. Verify: get_diagnostics + cargo check
5. Test: cargo test affected areas
```

## Performance Tips

- LSP queries on large codebases may take a few seconds
- Batch related queries in parallel when possible
- Use file_path hints to scope queries
- Restart LSP server (`mcp__cclsp__restart_server`) if results seem stale
- For very large result sets, combine with grep to filter

## Common Pitfalls

1. **Wrong symbol_kind**: Rust `trait` → use `interface`
2. **Stale LSP state**: After major changes, restart server
3. **Workspace scope**: LSP only sees files in the workspace
4. **Macro-generated code**: May not be fully visible to LSP
5. **Feature-gated code**: Ensure features are enabled in Cargo.toml
