## Common Workflows

### Rebuild System

```bash
cd /realm/project/sinnix
direnv allow                        # Activate devshell (provides switch, check, etc.)
switch                              # Build, evaluate, and activate immediately
```

All rebuild commands use `nh` under the hood (systemd-run containment, nice=10):

```bash
switch                              # nh os switch — build + activate
boot                                # nh os boot — build + set boot default (safer: reboot)
test-system                         # nh os test — build + activate without persisting
test-vm                            # nixos-rebuild test-vm — test in QEMU (nh doesn't wrap this)
clean                               # nh clean all — garbage collect + optimise
```

**For risky changes — test in VM first:**

```bash
test-vm                            # Build QEMU VM, launch it, verify interactively
switch                              # Apply to live system when confident
```

After activation, compare the closure diff:

```bash
diff-closure                        # Compare two most recent system profiles (nvd diff)
nvd diff /nix/var/nix/profiles/system-{N,N+1}-link  # Compare specific generations
nix-tree                            # Interactive dependency browser (find rebuild root causes)
```

### Pre-Flight Before Rebuild

Use `check --no-build` when you need a non-activating gate before committing or
when the user explicitly asks for a pre-flight. Do not run it before `switch`
when the user asks to apply a live repair now; `switch` already evaluates and
builds before activation, so a separate check only delays recovery. Avoid raw
`nix flake check --no-build` for routine pre-flight work on this host; that
traversal has filled zram and wedged in uninterruptible sleep. The curated check
catches:

- Option type errors and missing required arguments
- Coverage manifest consistency (services without coverage entries)
- Runtime surface invariant violations (duplicate units, kind mismatches, unknown resource classes)
- Module evaluation errors (stale option names, removed upstream interfaces)

### Agent Tool Updates

All three agent CLIs (Claude Code, Codex, Gemini) are FHS-bootstrapped via npm.
No Nix rebuild is needed — each agent self-updates natively inside its FHS environment:

- `claude update` updates `@anthropic-ai/claude-code` in `~/.local/state/claude-code/npm/`
- `codex update` updates `@openai/codex` in `~/.local/state/codex/npm/`
- `gemini update` updates `@google/gemini-cli` in `~/.local/state/gemini/npm/`

FHS state directories are persisted under `~/.local/state/{claude-code,codex,gemini}`,
surviving impermanence cold boots.

### Add New Feature

```bash
# 1. Create module
vim modules/features/desktop/new-feature.nix

# 2. Auto-discovered by default.nix — no wiring needed

# 3. Enable in host or bundle
vim hosts/sinnix-prime/default.nix  # Add to sinnix.features.desktop.new-feature

# 4. Test/apply
test-vm && switch

# 5. Update CLAUDE.md includes
vim .agent/includes/modules/features.md  # Add to feature list
```

### Add New Service

```bash
# 1. Create module
vim modules/services/my-service.nix

# 2. Auto-discovered — no wiring needed

# 3. Declare coverage in test-coverage.nix
vim flake/test-coverage.nix  # Add to services section

# 4. Enable in host
vim hosts/sinnix-prime/default.nix

# 5. Apply
switch
```

### Add New Package Overlay

```bash
# 1. Create overlay file
vim flake/overlay/package/my-package.nix

# 2. Add to overlay list
vim flake/overlay/package/default.nix  # Add to mkOverlay list

# 3. Test
nix build .#nixosConfigurations.sinnix-prime.config.system.build.toplevel
```

### Add New Script

```bash
# 1. Create script
vim scripts/my-script
chmod +x scripts/my-script

# 2. Add package wrapper
vim flake/packages.nix  # Add writeShellApplication entry

# 3. Test
nix run .#my-script
```
