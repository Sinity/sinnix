# Sinnix

Sinnix is the declarative NixOS and Home Manager configuration of the primary
workstation, and the home of `agentctl` (the CLI that runs declared project
operations and coding-agent batches) and the agent gateway. Keep configuration
declarative, generated surfaces reproducible, and host behavior observable.

## Public boundary

Tracked files, commits, task exports, and CI output are public. Never commit
secrets, decrypted values, private captures, generated personal state, or
machine-specific credentials. Secrets enter modules through declared secret
inputs.

## Layout

```text
flake/data/   small declarative registries (runtime defaults, MCP, agent lanes)
flake/tests/  evaluation and runtime contract checks
modules/      features/ (default-on), services/ (default-off), lib/ (factories)
pkgs/         agentctl/, sinnix-agent-gateway/, other real packages
scripts/      small independently packaged utilities
dots/         managed user configuration; dots/_ai/ holds the global agent
              instructions (AGENTS.md) and shared skills
```

- Nix modules own fixed services, packages, files, secrets, users, mounts, and
  activation. Systemd is the live process and service authority; do not
  duplicate its process tree, timeouts, or results in shell supervisors.
- `agentctl` owns project descriptors, the packet compiled from a task, the
  launch and result contract of a queued command, and the operator view
  (`docs/agentctl.md`). It does not own product-domain concurrency; Sinex's
  byte, rate, and destructive-operation budgets stay in Sinex.
- The gateway owns principal and capability policy and high-level machine and
  project tools (`docs/agent-gateway.md`). It calls agentctl's routes in
  process and never becomes a second job controller.

## Modules

- Use the factories: `mkFeatureModule` for default-on features,
  `mkServiceModule` for default-off services, `mkCaptureLane` for capture
  lanes, and `lib.sinnix.mkScheduledJob` for every scheduled oneshot (its
  registration provides failure notification and resource placement; never
  hand-wire a second timer or notifier). Bypassing a factory needs a
  structural reason. Plain helpers imported by a module stay out of
  auto-import sets.
- A module declares the options it implements. Registries describe
  capabilities and reject duplicate identities at evaluation; they do not copy
  effective systemd policy. Set a fixed service's resources on its own unit,
  and only where the service needs them.
- Every generated file has one declared source and one renderer; change the
  source, not the output. Dotfiles are owned through module metadata and the
  dotfile sweep, never as hand-managed copies.
- Every file under `scripts/` declares `@sinnix-package` frontmatter or
  `# @sinnix-package: skip`. Python imports go in `pythonPackages`, not
  `runtimeInputs`.
- Keep flake inputs pinned and overrides explicit.

## Resources and scheduling

- Declared operations choose a pueue group (`interactive`, `normal`, `bulk`,
  `pytest`, `agent`) whose width comes from `sinnix.services.agentctl.pools`
  and is applied with `agentctl pools apply`, never by restarting pueued.
  Backpressure pauses and releases groups through pueue.
- Memory is bounded by the slice hierarchy and the resource classes in
  `flake/data/runtime-defaults.nix`. Hard `MemoryMax` is reserved for explicit
  safety boundaries such as a batch worker's unit. The `bulk` group admits
  large Nix operations; nothing wraps `nix` by basename.
- Timers trigger declared operations: a descriptor's `schedule` becomes a
  transient timer running `agentctl job fire`, and a service module's timer
  runs `agentctl job start <project> <operation>`.
- Project MCP servers are launched from the generated client profiles
  (`flake/data/mcp-registry.nix`); do not configure them per client.

## Agent surfaces

The managed agent configuration stays small: the global instructions at
`dots/_ai/AGENTS.md` (linked as `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`,
and `~/.gemini/GEMINI.md`), shared skills under `dots/_ai/skills/`, agent
definitions and hooks under `dots/claude/`, the Polylogue capture hooks, one
destructive-command guard, and the agentctl job and batch lifecycle. Instruction
and skill text is live through symlinks; adding, renaming, or removing a skill
changes Codex's per-skill links only at activation. After a change to the skill
set, agent definitions, or MCP registry, regenerate `docs/agent-environment.md`
with `nix run .#sinnix-agent-environment-doc -- --output
docs/agent-environment.md`.

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

## Activation

A switch changes the live machine. Rebuild only through the devshell `switch`,
`boot`, or `test-vm` (`nix develop --command switch` from outside it), never a
bare `nh os switch` or a duplicate preflight evaluation. State the units,
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
