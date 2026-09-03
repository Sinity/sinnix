# Main checkout authority

Status: decided 2026-09-01. This is a decision record only. It does not move, delete, or chmod a checkout.

## Decision

Adopt a read-only, auto-synced reference checkout for project discovery and human reference reads. Keep mutable work in AgentCTL-managed worktrees. Git integration is owned by the active worktree plus AgentCTL's delivery route, with GitHub as publication authority. Beads task state is already owned by `/realm/state/tasks/sinnix/.beads`; the checkout path is only the caller context. The reference checkout remains the compatibility point during migration, then becomes a checked-out mirror whose working tree is never an edit surface.

This is the lowest-risk model that removes a privileged mutable checkout without removing a useful stable project reference. It preserves offline reads and bootstrap from a known tree, while making synchronization failure visible. The no-privileged-checkout model fails bootstrap and human-reference requirements unless every consumer first gains an explicit project source.

## Evidence and current authority

The descriptor at `.agentctl/project.toml:15-21` declares a `git-worktree` provider rooted at `/realm/worktrees` with `default_base = "origin/master"`. The project descriptor loaded by `agentctl project get sinnix` is `/realm/project/sinnix/.agentctl/project.toml`; it reports the same workspace policy and verification operations `check` and `lint`.

`docs/sinnixd.md:248-286` states that the configured project root is the registered default checkout, that workspace creation validates the configured root and base, and that publication requires an exact-head verification receipt before push and review creation. `pkgs/sinnixd/sinnixd/projects.py:1571-1588` currently requires the configured root to be a registered Git worktree and gives it checkout ID `default`. `pkgs/sinnixd/sinnixd/workspaces.py:752-760` resolves an omitted base from the descriptor, and `pkgs/sinnixd/sinnixd/delivery.py:49-72,415-419` derives the publication base branch from that same descriptor value.

The default-checkout API surface is broader than workspace creation. `pkgs/sinnixd/sinnixd/projects.py:1526-1588` discovers and returns the registered `default` checkout, `pkgs/sinnixd/sinnixd/service.py:853-899` selects it for declared and scheduled jobs when no workspace is supplied, and `pkgs/sinnixd/sinnixd/project_plans.py:565` uses it when a plan omits `checkout_id`. `pkgs/sinnixd/sinnixd/packets.py:231` resolves the project source used by packet compilation, while `pkgs/sinnixd/sinnixd/cli.py:1300-1418` routes lane, campaign, and packet commands through that resolver. These are current migration seams, not additional authorities.

Beads is path-independent for authority. `bd context --json` from this worktree reported `cwd_repo_root=/realm/worktrees/packet-sinnix-45vk`, `repo_root=/realm/project/sinnix`, `is_worktree=true`, and `beads_dir=/realm/state/tasks/sinnix/.beads`. The same command from `/realm/project/sinnix` reported `cwd_repo_root=/realm/project/sinnix`, `repo_root=/realm/state/tasks/sinnix`, `is_worktree=false`, and the same `beads_dir`. The differing `repo_root` field is Beads' repository-context result, not a second task database. No task command or Git mutation was performed.

The persistent checkout and this worktree were both at `8af9bb7c31c5cd30a31d357cbc47004c69fbfe3d`; `git rev-parse --verify origin/master` returned that commit from both roots. The persistent checkout had pre-existing modifications in `dots/claude/CLAUDE.md`, `flake/tests/runtime.nix`, `modules/services/lynchpin.nix`, `pkgs/chatgpt-app/default.nix`, `pkgs/sinnixd/sinnixd/cli.py`, and `pkgs/sinnixd/test_service.py`. The lane did not alter them.

## Routing probes

All commands below were run once from `/realm/worktrees/packet-sinnix-45vk` and once from `/realm/project/sinnix`, except where noted. They were read-only or rejected before state creation.

| Concern                       | Command and observed result                                                                                                                                                                                                                                                                                                                                  | Path dependence                                                                                             |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------- |
| Beads routing                 | `bd context --json`: both used `/realm/state/tasks/sinnix/.beads`; the worktree had `is_worktree=true`, while the persistent root had `is_worktree=false`.                                                                                                                                                                                                   | Caller metadata differs. Task authority is equal.                                                           |
| Workspace inventory           | `agentctl workspace list`: succeeded from both roots and returned the same registered workspace population. `git worktree list --porcelain` showed the persistent root plus linked worktrees under `/realm/worktrees`.                                                                                                                                       | AgentCTL service state is equal. Git's default worktree remains the configured root.                        |
| Workspace creation validation | `agentctl workspace create sinnix authority-probe --branch 'invalid branch' --base origin/master` returned `INVALID_ARGUMENT: workspace branch is invalid`, exit 1, from both roots. No target was created.                                                                                                                                                  | Equal validation. The command resolves through the daemon, not caller cwd.                                  |
| Base resolution               | `agentctl workspace create sinnix authority-probe --branch feature/authority-probe --base refs/does-not-exist` returned `INVALID_ARGUMENT: workspace base does not resolve to a commit`, exit 1, from both roots. `git rev-parse --verify origin/master` returned the same commit from both roots.                                                           | Equal descriptor/Git reference result. The configured project root is the Git authority used by the daemon. |
| Project discovery             | `agentctl project get sinnix` succeeded and reported root `/realm/project/sinnix`, descriptor `/realm/project/sinnix/.agentctl/project.toml`, workspace root `/realm/worktrees`, and default base `origin/master`.                                                                                                                                           | Explicitly path-bound today.                                                                                |
| Publication contract          | `agentctl workspace publish --help` succeeded from both roots. The interface requires a workspace ID, verifier job, title, and body. Source inspection confirms push and review creation run with the selected worktree as cwd, while base-branch derivation uses `workspace.default_base`. No publish was attempted because it pushes and creates a review. | Contract equal; descriptor root remains needed for ref and project lookup.                                  |

The two rejected create probes establish that validation happens before worktree creation. Post-probe `git worktree list --porcelain` contained no `authority-probe` path or branch.

## Dependency inventory

The required census command was run exactly as follows:

```text
rg -n '/realm/project/sinnix|default_base|workspace_root|projectRoot' .agentctl docs modules pkgs scripts dots flake
```

It returned 129 hits in 46 files. Seventeen hits are in this decision record itself, because the required search includes `docs/`. Those self-references are classified as evidence, probe, census, or residual-risk statements in this record. The remaining 112 hits in 45 other files are classified below. Line numbers are the output of that command at decision time.

### Authority and project discovery

- `.agentctl/project.toml:19,52,83`: descriptor default base and operations that explicitly read the persistent flake. Runtime project adapter input. Replace operation-specific paths with the reference source contract.
- `docs/sinnixd.md:44,46,167`: current project-root registration and examples. Documentation and live configuration example.
- `flake/command-registry.nix:118`: generated command reads configured `projectRoots`. Nix service integration.
- `modules/services/sinnixd.nix:16,26,57,59,104`: project-root option, uniqueness check, and daemon arguments. Service authority.
- `pkgs/sinnixd/sinnixd/projects.py:204,216,1118,1129,1130,1137,1138,1143,1145,1193,1194`: descriptor schema and project/workspace root parsing. Runtime project discovery.
- `pkgs/sinnixd/sinnixd/workspaces.py:688,752,1126,1225,1355,1373,1386,1399`: default checkout, base resolution, and default-base checks. Workspace/Git authority.
- `pkgs/sinnixd/sinnixd/delivery.py:49,241,415,416,419`: publication base and default-base validation. Delivery authority.
- `pkgs/sinnixd/sinnixd/review.py:158`: redflags script path. Review tooling path assumption.
- `pkgs/sinnixd/sinnixd/packets.py:378`: shared packet path construction. Packet runtime path assumption.
- `scripts/sinnix-lake-refs:48`: fixed repository map. Evidence tooling path assumption.
- `scripts/oracle:49`: fixed Git repository list. Operator/evidence entry path.
- `scripts/sinnix-census:58`: default repository environment value. Evidence tooling default.
- `scripts/sinnix-direnvrc:50,166,167`: root classification and fallback script lookup. Shell entry path.
- `scripts/sinnix-phone:431,677,769`: flake directory defaults and install route. Device operator entry path.
- `modules/foundation.nix:98,104`: `projectRoot` option and dots default. Nix configuration source.
- `modules/home-manager.nix:14`: flake path from `projectRoot`. Generated user configuration.
- `modules/services/terminal-capture.nix:16`: capture repository root from `projectRoot`. Service root.
- `modules/services/oracle.nix:60`: oracle script from `projectRoot`. Service root.
- `modules/features/cli/task-tracking.nix:44`: dots root from `projectRoot`. Generated user configuration.
- `modules/features/desktop/mime.nix:63`, `modules/features/desktop/browser.nix:41`, `modules/features/desktop/hyprland/default.nix:15`, `modules/features/desktop/hyprland/bindings.nix:14`: desktop scripts and roots from the configurable project root. Generated user configuration.

### Task routing and agent/operator entry paths

- `dots/codex/config.toml:32`: client project registration. Agent client entry path.
- `dots/claude/managed-settings.json:55,65,107,112,117,122`: hook commands. Agent client entry paths.
- `dots/claude/CLAUDE.md:114,146`: rebuild and campaign protocol examples. Agent documentation entry paths.
- `dots/_ai/skills/orchestrate/scripts/dispatch_lane:29`: worker contract path. Agent dispatch entry path.
- `dots/_ai/skills/desktop-control-plane/scripts/kitty-remote-control.sh:167`, `dots/_ai/skills/desktop-control-plane/SKILL.md:171`, `dots/_ai/skills/desktop-control-plane/references/control-recipes.md:40`: terminal fallback and examples. Desktop/operator entry paths.
- `dots/timewarrior/timewarrior.cfg:2,124,151`, `dots/timewarrior/extensions/on-modify.timewarrior:3`, `dots/taskwarrior/taskrc:2,6,78`: managed dotfile includes and hooks. Generated user configuration.

### Tests and fixtures

- `flake/tests/vm.nix:101,102,103,107,120,121,122,123,126,127,128,129,152,154,170,183`: VM fixture paths, fake runner, and default-checkout agent test. Test-only fixture; it must be updated with any topology migration.
- `flake/tests/cli.nix:116,126,142`: CLI fixture source paths. Test-only fixture.
- `flake/tests/bd-safety.sh:58,59`: safety fixture command strings. Test-only assertions of allowed command shape.
- `flake/tests/agent-tools.nix:705,770`: gateway/agent fixture checkout data. Test-only fixture.
- `flake/tests/kitty-agent-here.sh:44,62`: fallback cwd fixture. Test-only fixture.
- `pkgs/sinnixd/test_service.py:981`: descriptor fixture default base. Test-only fixture.
- `pkgs/sinnix-ops-reducer/tests/test_pages.py:134`, `pkgs/sinnix-ops-reducer/tests/test_actions.py:97,303`: reducer fixture checkout records. Test-only fixture.
- `docs/design/orchestration-next.md:101`, `docs/design/lane-lifecycle-prototype.py:40`: design/prototype assumptions. Non-runtime design inputs; update or retire during migration.
- `flake/treefmt.nix:9`: `projectRootFile = "flake.nix"`. Generic tool configuration; it does not privilege the persistent checkout.

The 17 self-referential hits in `docs/main-checkout-authority.md` are intentional record metadata: lines 13, 19, and 25 identify source evidence and probe scope; lines 33-34 identify observed paths and publication behavior; lines 43, 52, 65-69, 91, 101, and 116 preserve census classifications and decision comparison; line 132 records residual risk; and line 140 records the verification count. They do not represent runtime dependencies.

The census contains no Beads database path under the checkout. The canonical task store is supplied by runtime state and the `.beads/redirect` mechanism described in `docs/sinnixd.md:167` and the live `bd context` probes.

## Model comparison

| Criterion       | Current mutable primary                                                                                                         | Read-only auto-synced reference                                                                                                                   | No privileged checkout                                                                                                     |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Bootstrap       | Works if `/realm/project/sinnix` exists and has the descriptor; the root is also a writable Git worktree.                       | Works from the reference descriptor and a known `origin/master`; edits must start in a managed worktree.                                          | Requires discovery and descriptor acquisition before any project operation. No current bootstrap route proves that source. |
| Recovery        | A dirty or damaged primary can block identity checks and confuse human recovery.                                                | Re-sync or replace the reference, then recreate managed worktrees from the recorded base. Sync failure is visible and reversible.                 | Recovery needs an external source, then reconstruction of every project root and client path.                              |
| Synchronization | Human edits and service reads can observe different commits; there is no sync invariant.                                        | One writer updates the reference from the declared upstream; readers observe a known revision. A failed sync leaves the last known good revision. | Every consumer must resolve its own revision, creating multiple freshness policies.                                        |
| Dirty state     | Persistent dirty state is already observed and can affect tools that read the root.                                             | Reference is clean by contract; mutable state belongs to a worktree and is checked before publication.                                            | Dirty state is distributed across arbitrary caller directories and is harder to inventory.                                 |
| Task routing    | Beads already routes to `/realm/state/tasks/sinnix/.beads`; the primary path adds no authority.                                 | Same canonical task store and redirect behavior.                                                                                                  | Same task store is possible, but native callers still need a project root and redirect.                                    |
| Publication     | Current delivery can use the registered worktree and descriptor base, but the primary is also the project root used for lookup. | Delivery uses the selected managed worktree and `origin/master`; the reference supplies project metadata and refs.                                | Delivery can use a managed worktree, but project lookup and base verification need a new explicit source API.              |
| Offline use     | Best for human reads, but local edits can silently diverge.                                                                     | Good for reads at the last synchronized revision; publication waits for upstream reachability.                                                    | Poor until a source cache and explicit revision policy exist.                                                              |

The selected model has one owner per role:

| Role                  | Owner                                                                              |                                                   Writer count |
| --------------------- | ---------------------------------------------------------------------------------- | -------------------------------------------------------------: |
| Git integration       | AgentCTL-managed worktree, Git, and GitHub delivery                                | 1 active worktree writer; reference sync is separate and clean |
| Task routing          | `/realm/state/tasks/sinnix/.beads` through Beads                                   |                                                              1 |
| Project discovery     | Sinnix project adapter and the reference checkout                                  |                                            1 descriptor source |
| Service roots         | Nix `sinnix.paths.projectRoot` resolved to the reference checkout during migration |                                 1 declared configuration owner |
| Human reference reads | Read-only reference checkout                                                       |                                                              1 |

## Migration packets

Packets are ordered and independently reversible. No packet deletes the current primary until all later consumers have moved and a restore path is verified.

1. **Declare the reference contract.** Change `.agentctl/project.toml`, `modules/foundation.nix`, and the owning runtime/project-root registry so the reference path, sync command, revision marker, and clean-tree invariant are explicit. Verify `agentctl project get sinnix`, a clean reference status, and a failed-sync rollback to the previous revision. Rollback is restoring the descriptor and registry values.
2. **Separate project discovery from checkout identity.** Change `pkgs/sinnixd/sinnixd/projects.py`, `pkgs/sinnixd/sinnixd/workspaces.py`, and their focused tests so the reference is a source, while managed worktrees are the only mutable checkout records. Verify workspace create, adopt, base resolution, and `workspace list` from both roots. Rollback restores the current `default` checkout invariant.
3. **Move task and packet callers to canonical references.** Change `pkgs/sinnixd/sinnixd/packets.py`, `dots/_ai/skills/orchestrate/scripts/dispatch_lane`, Beads-facing client configuration, and related fixtures. Verify `bd context --json` from a managed worktree and the reference reports the same Beads directory, and verify packet paths never write task state into Git. Rollback restores the prior caller paths; the task database is untouched.
4. **Move fixed service and generated configuration roots.** Change `modules/services/sinnixd.nix`, `modules/services/terminal-capture.nix`, `modules/services/oracle.nix`, `modules/home-manager.nix`, desktop modules, `flake/command-registry.nix`, and generated config sources. Verify evaluated unit arguments and rendered file paths name the reference source, then run the service environment contract check. Rollback is the prior Nix configuration generation; no live switch is part of this decision.
5. **Move operator and client entry paths.** Change `scripts/sinnix-direnvrc`, `scripts/sinnix-phone`, `scripts/sinnix-lake-refs`, `scripts/oracle`, `dots/codex/config.toml`, Claude settings, time/task configuration, and desktop control references. Verify each entry path resolves the reference for reads and a managed worktree for writes. Rollback restores the prior client configuration files.
6. **Retire the privileged-primary invariant.** Only after packets 1-5 pass, change the default-checkout assumptions in `pkgs/sinnixd/sinnixd/projects.py`, delivery tests, VM fixtures, reducer fixtures, and design references. Verify a clean reference with a managed worktree can bootstrap, publish through a verifier receipt in a test environment, recover a missing managed worktree, and preserve the Beads authority. Rollback is the last known-good reference and a re-enabled primary registration. Blocker: the reference sync mechanism, service activation policy, or explicit project-source API must exist before this packet starts.

## Residual risk

The selected model is not implemented by this bead. Until packet 4 lands, fixed services and generated dotfiles still encode `/realm/project/sinnix`; until packet 2 lands, runtime discovery still requires that path to be a registered default checkout. The persistent checkout is currently dirty, so any migration must preserve its changes or obtain explicit operator handling. Publication also still depends on GitHub reachability and a successful exact-head verifier receipt.

## Verification record

Required commands and results:

- `agentctl workspace list`: exit 0 from the lane worktree and persistent checkout.
- `bd context --json`: exit 0 from both roots; both reported `/realm/state/tasks/sinnix/.beads`.
- `rg -n '/realm/project/sinnix|default_base|workspace_root|projectRoot' .agentctl docs modules pkgs scripts dots flake`: exit 0; 129 hits in 46 files, consisting of 112 source hits in 45 other files plus 17 classified self-references in this record.

Additional probes were the two rejected `agentctl workspace create` commands, `agentctl project get sinnix`, `agentctl workspace publish --help`, `git rev-parse --verify origin/master`, `git status --short --branch`, and `git worktree list --porcelain`. No task, checkout, service, or live configuration state was mutated.
