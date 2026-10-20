# Sinnix

Sinnix owns NixOS and Home Manager configuration, `agentctl` project operations
and agent batches, and the agent gateway. Keep configuration declarative and
generated files reproducible; verify host changes against live behavior.

## Public boundary

Tracked files, commits, task exports, and CI output are public. Never commit
secrets, decrypted values, private captures, generated personal state, or
machine-specific credentials. Secrets enter modules through declared secret
inputs.

## Layout

```text
flake/data/   small declarative registries (runtime defaults, MCP, agent launcher profiles)
flake/tests/  evaluation and runtime contract checks
modules/      features/ (default-on), services/ (default-off), lib/ (factories)
pkgs/         packages (agentctl/, sinnix-agent-gateway/, ...); a pkgs/<name>/
              holding only tests/ is the test suite for scripts/<name>
scripts/      small independently packaged utilities
dots/         managed user configuration; dots/_ai/ holds the global agent
              instructions (AGENTS.md) and shared skills
```

- Nix modules declare services, packages, files, secrets, users, mounts, and
  activation. Systemd owns live processes, timeouts, and results; shell
  supervisors must not duplicate that state.
- `agentctl` owns project descriptors, the worker prompt built from a task,
  the launch and result contract of a queued command, and the operator view
  (`docs/agentctl.md`). It does not own product-domain concurrency; Sinex's
  byte, rate, and destructive-operation budgets stay in Sinex.
- The gateway owns who may call which tool, and the high-level machine and
  project tools (`docs/agent-gateway.md`). It calls agentctl's routes in
  process and never becomes a second job controller.
- A _receipt_ records a job, action, or backup outcome as JSON; read it rather
  than re-running work. A _capture lane_ is a captured stream under `/realm`
  and its producer unit.

## Modules

- Use the factories: `mkFeatureModule` for default-on features,
  `mkServiceModule` for default-off services, typed `sinnix.capture.producers`
  for unit-owned capture, and `lib.sinnix.mkScheduledJob` for scheduled oneshots (its
  registration provides failure notification and resource placement; never
  hand-wire a second timer or notifier). Bypassing a factory needs a
  structural reason. Plain helpers imported by a module stay out of
  auto-import sets.
- A module declares the options it implements. Registries describe
  capabilities and reject duplicate identities at evaluation; they do not copy
  effective systemd policy. Set a fixed service's resources on its own unit,
  and only where the service needs them.
- Do not sandbox sinnix's own units (`ProtectSystem`, `ProtectHome`,
  write-path lists, syscall filters): a refused write fails silently. Upstream
  nixpkgs module hardening stays as shipped, and a root-run tool that deletes
  files keeps a narrowed write scope.
- Every generated file has one declared source and one renderer; change the
  source, not the output. Dotfiles are owned through module metadata and the
  dotfile sweep, never as hand-managed copies.
- Every file under `scripts/` declares `@sinnix-package` frontmatter or
  `# @sinnix-package: skip`. Python imports go in `pythonPackages`, not
  `runtimeInputs`.
- Keep flake inputs pinned and overrides explicit.

## Resources and scheduling

- Declared operations choose a pueue group; the groups and their widths are
  `sinnix.services.agentctl.pools` (`modules/services/agentctl.nix`), applied
  with `agentctl pools apply`, never by restarting pueued.
  `agentctl pressure tick` pauses and reopens groups through pueue.
- Memory is bounded by the slice hierarchy and the resource classes in
  `flake/data/runtime-defaults.nix`. Hard `MemoryMax` is reserved for explicit
  safety boundaries such as a batch worker's unit. The `bulk` group admits
  large Nix operations; nothing wraps `nix` by basename.
- Scheduled work is a module's `mkScheduledJob` timer. When the work is a
  declared operation, its command is
  `agentctl job start --if-idle <project> <operation>`.
- Project MCP servers are launched from the generated client profiles
  (`flake/data/mcp-registry.nix`); do not configure them per client.

## Agent configuration

`dots/_ai/AGENTS.md` supplies global instructions through the Claude, Codex,
and Gemini home links. `dots/_ai/skills/` supplies shared procedures;
`dots/claude/` holds agent definitions, settings, and hooks. Capture hooks,
the destructive-command guard, and agentctl own their respective behavior.
Instruction and skill text is live through symlinks; Codex's per-skill links
change at activation when a skill is added, renamed, or removed.

After changing the skill set or descriptions, agent definitions, or MCP
registry, regenerate `docs/agent-environment.md`:

```sh
nix run .#sinnix-agent-environment-doc -- --output docs/agent-environment.md
```

## Workflow and verification

Sinnix publishes to `master` directly: verify, commit on `master` (or
fast-forward a short-lived branch), and push. No PRs; hosted CI does not gate
this repository. Worktrees remain the isolation for in-flight work.

- Short checks run from the devshell. Heavy checks run as declared operations:
  `agentctl job start sinnix lint`, `agentctl job start sinnix check`
  (`agentctl project operations sinnix` lists the rest).
- Use the narrowest check that proves the changed contract. For a module
  change, inspect the evaluated option, unit, or file, not just the source
  expression; for a registry, test duplicate rejection and source-to-output
  synchronization. Verify a deletion by evaluation, build, or runtime behavior
  plus a source census, never by a test that an old spelling is absent.
- Each commit message has a body that says why. A commit that only bumps
  `flake.lock` is titled `chore(inputs): ...`, never `fix(<area>)`.

## Activation

A switch changes the live machine. Rebuild only through the devshell `switch`,
`boot`, `test-system`, or `test-vm` (`nix develop --command switch` from
outside it; `agentctl job start sinnix switch` queues the same command), never
a bare `nh os switch` or a duplicate preflight evaluation. State the units,
files, mounts, or packages affected first. Afterwards compare
`nixos-version --configuration-revision` with the intended commit and check
the direct live fact (unit generation, executable path, rendered file). Do not
restart services, remove persistent state, or change storage layouts without
explicit authority and preservation checks.

## Documentation

`README.md` is the external overview; module headers and `docs/` hold
architecture; `docs/agentctl.md` holds agentctl verbs and the descriptor
schema; `docs/agent-gateway.md` and its generated reference hold the gateway
contract. This file is not an inventory of packages, wrappers, services, or
incidents; those are discoverable from code and `agentctl`.
