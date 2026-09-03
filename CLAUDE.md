# Sinnix

Sinnix is the declarative NixOS/user-environment configuration for the primary
workstation and the home of `agentctl`, the CLI that queues declared project
operations and runs coding-agent lanes. Keep configuration declarative,
generated surfaces reproducible, and host behavior observable without encoding
operational rituals in agent prose.

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
  sinnixd/              agentctl: jobs over pueue, lanes over worktrunk, gh and bd
  sinnix-agent-gateway/ typed gateway transport, policy, and action catalog
scripts/                small independently packaged utilities
dots/                   managed user configuration and agent instructions
```

The ownership boundaries are:

- Nix modules own fixed services, packages, files, secrets, users, mounts, and
  activation.
- `agentctl` owns the project descriptors, the prompt compiled from a bead,
  the launch-input and result-artifact contract of a queued command, and one
  operator screen. pueue owns the queue and every process; worktrunk owns
  worktrees; GitHub owns PRs and merge; Beads owns tasks.
- The gateway owns principal/capability policy and high-level machine/project
  tools; it calls agentctl's launch and lane routes in process and does not
  implement another job controller.
- Project descriptors (`.agentctl/project.toml`) own repository semantics:
  environment, declared operations, result parsing, lane defaults.
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

## `agentctl` boundary

`agentctl` is an in-process CLI (`docs/sinnixd.md`). A job is a pueue task in
the operation's pool; a lane is a worktrunk worktree with an agent in it and a
PR that merges itself. Verbs: `project`, `job`, `lane`, `refill`, `view`,
`events`, `schedule`.

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
- no orphan MCP sweeper.

## Resource policy

Declared operations choose a pueue group (`interactive`, `normal`, `bulk`,
`pytest`, `agent`). The group bounds concurrency; `sinnixd-backpressure.timer`
pauses groups under sustained host IO or memory stall; memory is bounded by
the slice hierarchy, not by per-job arithmetic. Fixed runtime surfaces use the
resource classes and slice budgets declared in
`flake/data/runtime-defaults.nix`; do not restate those values here.

Hard `MemoryMax` is reserved for explicit safety boundaries (an agent lane's
scope). Environment construction, scratch ownership, logging, timeout,
cancellation, and process cleanup are common runtime policy, not project
recipes.

Nix build concurrency remains a Nix concern. The `bulk` group controls how many
large Nix operations enter the machine; nothing wraps `nix` commands by
basename.

## Fixed services and scheduled operations

Fixed services remain ordinary NixOS/Home Manager units. Define direct resource
settings only where the service itself requires them.

Project MCP servers are launched by the clients' generated MCP profiles
(`flake/data/mcp-registry.nix`); do not duplicate project-server launch
configuration per client.

Timers trigger declared operations, not execution mechanics: a descriptor's
`schedule` field becomes one transient timer running `agentctl job fire`, and a
service module's timer submits `agentctl job start <project> <operation>`.
pueue owns queueing, logs, limits, and completion.

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
- Runtime inventory contains fixed services and captures, not copied
  resource-class inheritance.

## Agent surfaces

The managed agent configuration should be small:

- one global `CLAUDE.md` symlinked for supported clients;
- compact project skills plus common runtime/review/investigation skills;
- Polylogue capture hooks;
- one destructive-command guard;
- the shared `agentctl` job and lane lifecycle.

Model/effort is a field of every lane launch. The event spool records every
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
wt switch --create <branch> --no-cd -y
```

The project descriptor supplies the exact Nix environment and commands. Never
hand-reconstruct a service environment or invoke `systemd-run` for a project
check.

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
- `agentctl` verbs and the project descriptor schema: `docs/sinnixd.md`;
- gateway capability contract: `docs/agent-gateway.md` and its generated reference;
- agent skills: `dots/_ai/skills/`.

Do not make `CLAUDE.md` an inventory of every package, wrapper, service, or
historical incident. Those surfaces must be discoverable from code and
`agentctl`.
