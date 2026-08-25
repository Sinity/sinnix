# Sinnix

Sinnix is the declarative NixOS/user-environment configuration for the primary
workstation and the home of the common local execution/workspace service,
`sinnixd`. Keep configuration declarative, generated surfaces reproducible, and
host behavior observable without encoding operational rituals in agent prose.

## Public boundary

Treat every tracked file, commit, task export, CI result, and PR discussion as
public. Do not commit secrets, decrypted values, private captures, generated
personal state, machine-specific credentials, or unrelated operator data.
Secrets enter modules through declared secret/configuration inputs. Review the
complete staged diff before publication.

## Architecture

```text
flake/
  data/                 small declarative registries and generated inputs
  tests/                evaluation/runtime contract checks
modules/
  features/             user-facing workstation capabilities
  services/             fixed system/user services
  lib/                  module factories and shared Nix helpers
pkgs/
  sinnixd/              common job/workspace/agent/service/task runtime
  sinnix-agent-gateway/ typed gateway transport, policy, and action catalog
scripts/                small independently packaged utilities
dots/                   managed user configuration and agent instructions
```

The ownership boundaries are:

- Nix modules own fixed services, packages, files, secrets, users, mounts, and
  activation.
- `sinnixd` owns transient jobs, queueing, resource admission, workspaces,
  coding-agent sessions, on-demand local services/MCP leases, and task-backend
  access.
- The gateway owns principal/capability policy and high-level machine/project
  tools; it calls `sinnixd` for execution and does not implement another job
  controller.
- Project adapters own repository semantics such as setup, checks, result
  parsing, fingerprints, and conflict keys.
- Systemd remains live process/service authority. Do not duplicate its process
  tree, timeout, signal, or result state in shell supervisors.

## Module taxonomy

Use the established factories unless a module truly does not fit:

- `mkFeatureModule` for default-on user-facing features;
- `mkServiceModule` for default-off fixed services and their standard integration;
- `mkCaptureLane` for capture lanes with shared ownership/hardening semantics.

Every scheduled oneshot is rendered through `lib.sinnix.mkScheduledJob`,
directly or through a service module's `job` argument. Runtime registration is
the source of failure notification and resource placement; do not hand-wire a
second timer pair, failure notifier, or per-unit resource policy.

A factory bypass must have a structural reason, not convenience. Plain-Nix
helpers imported by a module are not standalone modules and must not appear in
auto-import sets.

Keep option ownership local:

- options are declared by the module that implements them;
- generated files have one declared source and one renderer;
- registries describe capabilities, not duplicate effective systemd policy;
- fixed-service settings are written directly on the owning unit when they are
  semantically required.

## `sinnixd` boundary

The runtime exposes one Unix-socket API and `agentctl` CLI. It owns:

- jobs and dependencies;
- adaptive host resource admission;
- worktree/workspace lifecycle and checkpoints;
- coding-agent backend/session binding;
- on-demand local service leases;
- task-backend adapters;
- structured state for the hub/gateway.

It does not own product-domain concurrency. For example, Sinex work-item byte,
rate, and destructive-operation budgets remain inside Sinex.

Do not recreate any of the retired forms:

- no public `sinnix-scope`;
- no `sinnix-agent-scope-exec`;
- no command-basename interception in direnv;
- no static command classes or per-agent memory envelopes;
- no gateway-local job manifests;
- no job/instance controller scripts in skills;
- no process ownership inferred from command lines;
- no orphan MCP sweeper after service-lease cutover.

## Resource policy

Declared operations choose the `normal` or `bulk` admission pool and provide
memory estimates, scratch placement, and exact conflict keys. Sinnixd admits
them against live host pressure and owns their transient systemd units. Fixed
runtime surfaces use the resource classes and slice budgets declared in
`flake/data/runtime-defaults.nix`; do not restate those values here.

Hard `MemoryMax` is reserved for explicit safety boundaries. Environment
construction, scratch ownership, logging, timeout, cancellation, and process
cleanup are common runtime policy, not project recipes.

Nix build concurrency remains a Nix concern. The scheduler controls how many
large Nix operations enter the machine; it does not wrap every `nix` command by
basename.

## Fixed services and on-demand services

Fixed services remain ordinary NixOS/Home Manager units. Define direct resource
settings only where the service itself requires them.

Project MCP servers and optional developer services are registered as
`sinnixd` service specs. They start on first lease, remain shared while leased,
and stop after bounded idle time. Clients normally connect through the single
Sinnix MCP frontend; do not duplicate project-server launch configuration in
Claude, Codex, Gemini, VS Code, and the gateway.

Timers should trigger semantic operations, not reproduce execution mechanics.
For example, a timer may submit `sinex:cache-prebuild` keyed by the locked Sinex
revision or `lynchpin:materialize-default`; the runtime owns deduplication,
queueing, logs, limits, and completion.

## Configuration and generated surfaces

- Keep flake inputs pinned and overrides explicit.
- Do not edit generated files without changing their declared source/renderer.
- Keep script package metadata (`@sinnix-package`) on independently packaged
  scripts. Every file under `scripts/` declares frontmatter or explicitly uses
  `# @sinnix-package: skip`; Python imports belong in `pythonPackages`, not
  `runtimeInputs`.
- Dotfile entries are owned through module metadata and rendered by the
  dotfile sweep. Avoid parallel hand-managed copies.
- Port, project, service, MCP, and capture registries must reject duplicate
  identities during evaluation.
- Runtime inventory contains fixed services/captures and current `sinnixd`
  endpoint metadata, not copied resource-class inheritance.

## Agent surfaces

The managed agent configuration should be small:

- one global `CLAUDE.md` symlinked for supported clients;
- compact project skills plus common runtime/review/investigation skills;
- Polylogue capture hooks;
- one destructive-command guard;
- the shared AgentCTL workspace and job lifecycle.

Model/effort is a field of the agent launch request. The daemon records every
launch. Do not maintain shell-parsed dispatch ledgers or subagent stop ledgers.

## Development workflow

This repository publishes from `master` directly: verify locally, commit on
master (or land a short-lived branch with a plain merge/fast-forward), push.
Do not open GitHub PRs for sinnix work — hosted CI does not run automatically
here and PR ceremony adds review latency with no gate behind it. Worktrees
and branches remain fine as isolation for in-flight work; they end in a
direct push, not a PR.

Short foreground work may use ordinary commands from the devshell. Durable or
heavy operations use project operations:

```bash
agentctl project operations sinnix
agentctl job start sinnix check
agentctl job start sinnix lint
agentctl workspace create sinnix <name> --branch feature/<name>
agentctl workspace land <workspace-id> --job <verified-job-id>
```

The Sinnix project adapter supplies the exact Nix environment and commands.
Never hand-reconstruct a service environment or invoke `systemd-run` for a
project check.

## Verification

Use the narrowest check that proves the changed contract, then the default
semantic tier once at the change boundary.

Core checks:

```bash
agentctl job start sinnix lint
agentctl job start sinnix check
```

For module changes, inspect the evaluated unit/file/option rather than only the
source expression. For service changes, verify the rendered unit and, when
activation is authorized, the live unit state. For generated registries, test
duplicate rejection and source-to-output synchronization.

Do not add tests that merely require an old spelling to disappear. Deletion is
verified by evaluation/build/runtime behavior plus a final source census.

## Activation and destructive changes

A configuration switch changes the live machine. State the intended units,
files, mounts, or packages affected before activation. After activation,
verify the direct live fact (unit generation, executable path, mount, rendered
file), not merely command exit status.

Run rebuilds only through the devshell commands `test-vm`, `switch`, or `boot`
(`nix develop --command switch` from outside it). Do not run bare `nh os
switch` or preflight it with a duplicate evaluation. After every switch,
compare `nixos-version --configuration-revision` with the intended Sinnix
commit; command success alone does not prove activation.

Do not restart services, remove persistent state, or alter storage layouts
without explicit task authority and direct preservation checks.

## Documentation ownership

- external overview: `README.md`;
- module/service architecture: owning module headers and `docs/`;
- runtime API and project adapter schema: `docs/sinnixd.md`;
- gateway capability contract: `docs/agent-gateway.md` and its generated reference;
- agent skills: `dots/_ai/skills/`.

Do not make `CLAUDE.md` an inventory of every package, wrapper, service, or
historical incident. Those surfaces must be discoverable from code and
`agentctl`.
