# Sinnix Configuration

> **Working contract for agents editing this repo** — the NixOS system
> configuration for `sinnix-prime` (workstation), `sinnix-ethereal` (Hetzner
> replica), and `sinnix-gw` (OpenWrt router). Single flat file, no
> transclusion; `AGENTS.md` is a committed symlink to this file. Update this
> file in the same commit as any structural change it describes.
>
> Deep architecture and machine maps live in `.agent/scratch/`
> (`*-sinnix-architecture-grok.md`, `*-machine-map.md`) — read them when you
> need evidence-level detail beyond this contract.

---

## Operational Loop (Silent, Every Reply)

- Reconfirm requested scope and explicit constraints.
- Reconfirm module placement against taxonomy before editing.
- Reconfirm no compatibility aliases/shims are introduced.
- Reconfirm existing scripts/skills were checked before adding new helpers.
- Reconfirm commit boundary is coherent and validated.
- For live desktop/system repairs, if the user asks to apply or switch now,
  run `switch` directly. Do not insert `check --no-build` first; `switch`
  already evaluates/builds before activation.
- For Sinnix NixOS config edits, do not run standalone `nix eval`,
  `nix build`, or flake-check probes as agent hygiene unless the user
  explicitly asks for that diagnostic. They are slow on this host and repeat
  work that `switch` performs through the intended resource wrapper.
- If `switch` already evaluated/built and failed only during activation, fix the
  activation blocker and rerun `switch`. Do not add an intervening
  `check --no-build`; it repeats evidence already gathered while delaying
  recovery and adding load to a possibly degraded host.

## Beads Issue Tracking

This repository uses `bd` (Beads) for durable project task tracking.

- Run `bd prime` when task context, ready work, blockers, or durable project
  memory matter.
- Use `bd ready --json`, `bd show <id> --json`, `bd update <id> --claim --json`,
  and `bd close <id> --reason "..." --json` for tracked work.
- Create linked Beads issues for discovered follow-up work instead of leaving
  markdown TODO lists as the source of truth.
- `bd dolt push` follows the same repo policy as `git push`: Sinnix may push
  verified `master` work directly; do not bypass explicit hold instructions.

## Public Repository Boundary

Assume every tracked file, commit, branch, tag, Beads issue, Actions log, and
GitHub discussion is public.

- Machine-specific configuration and the operator's ordinary public identity
  are intentional repository content. Secrets, private datasets, raw captures
  or exports, private narratives or transcripts, and unrelated personal
  information are not.
- `.agent/scratch/`, `.agent/ops/`, root `.claude/`, root `.mcp.json`,
  `dots/codex/skills/.system/`, secret payloads, and
  `.beads/interactions.jsonl` are local-only. The Codex system-skill tree is
  tool-managed checkout state, not project source. Promote reusable technical
  conclusions into reviewed source, documentation, or Beads issues.
- Beads `issues.jsonl` is public technical archaeology; all of its fields must
  satisfy the same publication boundary as source and documentation.
- Before every commit, review the complete staged diff and run
  `scripts/check-publication-boundary`. The checker only catches known path and
  file shapes; it cannot judge prose, fixtures, or arbitrary data.
- If there is any doubt whether content belongs in the public repository,
  confirm with the operator before committing it.
- Publish only `master`. Never push `--mirror`, `--all`, or `--tags`; any new
  branch or tag requires an explicit publication review first.
- If private material was committed, stop publication, rotate any live secret,
  rewrite the allowed branch, and verify a fresh clone. Deleting the current
  file does not remove it from history.

## No-Alias Rule

- Do not preserve deprecated compatibility interfaces for renamed
  files/modules/options/commands.
- Apply full rename and reference updates in one pass.

---

## Architecture Map

Evaluation pipeline: `flake.nix` (flake-parts) → `flake/nixos.nix` `mkHost` →
`flake/lib-context.nix`, which builds the extended lib (`lib.sinnix.*`) and
`specialArgs`:

- `mkFeatureModule` / `mkServiceModule` — module factories
  (`modules/lib/features.nix`), injected directly into specialArgs.
- `helpers.data` — pure data tables from `flake/data/` (`mcpRegistry`,
  `runtimeDefaults`), evaluated once at flake init and shared by reference.
  Modules consume them via specialArgs; never re-`import` the data files.
- `helpers.mkSinnixPackagesFor pkgs` — the script package set (see Scripts).
- `lib.sinnix` — factory helpers, `systemd` hardening helpers,
  `mkRuntimeServiceConfig`, `mkAutoImports`, overlay helpers.

`modules/default.nix` auto-imports every module via
`lib.sinnix.mkAutoImports ./. [ "lib" "attic" ]` — new modules need zero
wiring. `modules/attic/{cold,museum}/` holds retired capabilities that are
deliberately not part of the default host character.

## Module Taxonomy

```
modules/
├── *.nix              # Infrastructure & platform (system-level)
├── features/          # User-facing capabilities (what users interact with)
├── services/          # Long-running systemd daemons
├── profiles/          # Host-shape defaults (cloud.nix headless, workstation.nix desktop)
└── lib/               # Helper functions (not modules)
```

Decision tree:

```
MATCH config_type:
  | System infrastructure (networking, storage, nix settings) → modules/*.nix
  | User-facing application or capability → modules/features/{cli,desktop,dev,system}/*.nix
  | Systemd daemon (primary purpose is background service)    → modules/services/*.nix
  | Host-shape defaults for a deployment class                → modules/profiles/*.nix
  | Reusable helper function                                  → modules/lib/*.nix
```

Boundary rules:

- If it affects **how the system operates**, it's top-level infrastructure.
  If users **directly interact** with it, it's a feature. If its primary
  purpose is a **daemon** (UI secondary), it's a service.
- Top-level highlights: `foundation.nix` (user/paths/projects identity),
  `build-policy.nix` (nix daemon: max-jobs=1/cores=16, build scratch at
  `/var/cache/nix-build`), `runtime.nix` (runtime inventory — see below),
  `persistence.nix` (impermanence collector), `backup.nix` (btrbk→Borg
  pipeline), `secrets.nix` (agenix auto-discovery), `dotfiles-sweep.nix`,
  `introspection.nix` (`/etc/sinnix/config.json`). Desktop resource
  governance (slices, sysctls, earlyoom, io.cost init) lives in
  `profiles/workstation.nix`, not a top-level module — see below.

## Factory Contracts

- **Features are default-ON.** `mkFeatureModule` sets `enable.default = true`:
  anything in `modules/features/` is unconditionally part of a sinnix host's
  default character. Hosts express *exceptions*
  (`sinnix.features.<path>.enable = false`) and configuration detail, not
  enables. Capabilities that should not be default-on belong in
  `modules/attic/`, not behind a disabled feature.
- **Services are default-OFF.** `mkServiceModule { name, surface, ... }`
  creates `sinnix.services.<name>`; hosts opt in. The optional `surface`
  argument auto-registers the unit in `sinnix.runtime.surfaces` so resource
  governance is co-located with the declaration.
- `subFeatures = { x = { description; default; }; ... }` generates nested
  `<feature>.x.enable` toggles (see `features/dev/shell.nix`).
- `meta.dotfiles.{configFile,dataFile,homeFile}` entries are collected by
  `modules/dotfiles-sweep.nix` into HM out-of-store symlinks pointing at
  `dots/<rel>`. String value ⇒ simple symlink; attrset ⇒
  `{ source; recursive; force; }`.
- Composite-module exception: `features/desktop/hyprland/` does not use
  `mkFeatureModule` (multi-file, tightly coupled system+HM config). Reserve
  that shape for WM-level complexity.
- Hermetic tests for modules live in `flake/tests-runtime.nix` using
  `flake/test-lib.nix` (`mkFeatureTest`, `mkHmRuntimeCheck`, `mkVmCheck`,
  `sanitizedInputs`, `mountTmpfsRoots`).

## Runtime Governance

One contract governs unit placement and observability:

- `flake/data/runtime-defaults.nix` defines resource **classes**
  (interactive-access, observability, capture-runtime, capture-substrate,
  backup-maintenance, background-maintenance, developer-build, system),
  command classes (agent/build/background/nix-build → slices), slice budgets
  (agent.slice is protected CPUWeight=400/MemoryLow=3G; build/nix-build are
  sacrificial MemoryHigh=22G/Max=28G), and the env allowlist.
- Modules declare `sinnix.runtime.surfaces.<name> = { unit, manager, kind,
  resourceClass, observe, captures }`. Eval-time assertions reject duplicate
  units, kind/suffix mismatches, and unknown classes.
- `lib.sinnix.mkRuntimeServiceConfig { runtimeInventory; unit; }` resolves a
  unit to its class serviceConfig (as mkDefault) and **throws on unknown
  units** — register the surface first.
- The whole inventory is serialized to `/etc/sinnix/runtime-inventory.json`,
  consumed at runtime by `sinnix-scope`, `sinnix-observe`, and machine
  telemetry. When adding a daemon: declare the surface, apply
  `mkRuntimeServiceConfig`, done — no ad-hoc Nice/IOWeight overrides.

## Flake Layout & Input Pinning

`flake/`: `nixos.nix` (hosts), `lib-context.nix` (shared bootstrap),
`dev-shell.nix` + `command-registry.nix` (rebuild commands — single source of
truth for lock/containment/preflight shared by devshell binaries and
`nix run .#switch`), `scripts.nix` + `script-discovery.nix` (script registry),
`packages.nix` (public package surface), `tests.nix` + `tests-runtime.nix` +
`test-lib.nix`, `router.nix` (sinnix-gw), `deploy.nix` (colmena +
nixos-anywhere), `overlay/package/*.nix` (per-package overlays),
`data/*.nix` (pure data: MCP registry, runtime defaults, shared skill list).

Overlays vs packages: override/patch an existing nixpkgs package → overlay
file; new standalone tool → usually a script under `scripts/` (see below),
or `pkgs/<name>/` for real derivations.

**Input pinning rules (cache-hit engineering — do not "fix" these):**

- `nixpkgs-ai` is a second, unfollowed nixos-unstable pin feeding the
  CUDA-narrowed AI packages (`flake/overlay/package/local-ai.nix`,
  `pkgsForCudaArch.sm_86`). Routine `update` (devshell command) deliberately
  excludes it; bumping it forces an hours-long CUDA recompile. Bump only via
  `update nixpkgs-ai`.
- `sinex` deliberately does NOT follow sinnix's nixpkgs, so its derivation
  hash stays stable across sinnix nixpkgs bumps and each sinex rev is
  compiled at most once. sinex CI no longer pushes to sinity.cachix.org
  (sinex#883 disabled automatic hosted Actions): the desktop is the builder
  of record, and `switch` publishes the sinex closure to the cache after a
  successful activation (`sinexCachePush`, flake/command-registry.nix).
- `lynchpin` is a local `git+file://` input; sinex/polylogue/scribe-tap/
  yt-polisher come from GitHub so deploys don't consume local checkout state.
  One-off local testing: `SINNIX_{SINEX,POLYLOGUE,LYNCHPIN}_OVERRIDE=<path>
  switch` (wired as `--override-input --no-write-lock-file`).

## Scripts

Source lives in `scripts/`; packaging is automatic via
`flake/script-discovery.nix`. **Every file in `scripts/` MUST carry
frontmatter** or evaluation fails:

```
# @sinnix-package
# description: One-line description (required)
# runtimeInputs: bash coreutils jq        # space-separated; @name = sibling script
```

or, for scripts launched directly (Hyprland keybindings, shell-sourced):

```
# @sinnix-package: skip
```

There is no manual wrapper registration. `flake/scripts.nix` only adds
non-script externals (lynchpin/polylogue pythons, vendored npm CLIs, beads);
`flake/packages.nix` curates the small public `nix run` surface.

## Dotfiles & Agent Context

- Everything in `dots/` reaches `$HOME` via HM out-of-store symlinks
  (`mkDotsFileFor` or `meta.dotfiles`) — edits propagate instantly, no
  rebuild. Never manage `dots/claude/settings.json` through HM store files;
  it is linked writable during activation (tested invariant).
- `dots/claude/CLAUDE.md` is the **global** agent instruction file (flat, no
  transclusion). `~/.codex/AGENTS.md` and `~/.gemini/GEMINI.md` are symlinks
  to it via `~/.config/claude/CLAUDE.md`. There is no render pipeline.
- Repo convention across the constellation: per-repo `CLAUDE.md` is canonical
  and flat; `AGENTS.md` is a committed symlink to it. Audit with
  `verify-agent-topology /realm/project`.
- Shared skills live in `dots/_ai/skills/`; agent trees (`~/.config/claude/
  skills`, `~/.codex/skills`, `~/.gemini/skills`) are linkFarms over it.
  Codex-only system skills: `dots/codex/skills/.system/`.
- MCP registry: `flake/data/mcp-registry.nix` (servers, tiers,
  lean/evidence/full/browser profiles, per-client render). Wiring + agent CLI
  wrappers live in `modules/features/dev/agents/` (regrouped from the former
  `agent-tools.nix`/`mcp-servers.nix`, sinnix-9u6): `clis.nix`
  (`sinnix.features.dev.agentTools`) + `backends.nix` own the CLI wrapper
  builders (npm-bootstrapped into `~/.local/state/<agent>/npm`, self-updating;
  `claude` aliases `claude-full` because the upstream installer clobbers the
  bare path); `mcp.nix` (`sinnix.features.dev.mcp-servers`) + `mcp-tools.nix`/
  `client-profiles.nix`/`serena.nix`/`browser.nix`/`hooks.nix` own the MCP
  registry wiring and per-client (Codex/Gemini) config generation. Only
  `clis.nix`/`mcp.nix` are real NixOS modules; the sibling files are plain-nix
  helpers imported directly, not auto-imported.

## Secrets

`modules/secrets.nix` auto-discovers `secret/*.age`: each file becomes an
`age.secrets` entry at `/run/agenix/<name>` (owner sinity, 0400 unless
special-cased) plus a shell export `<NAME_UPPER_SNAKE>` via
`/etc/profile.d/agenix-secrets.sh` (passwords/PSKs excluded). agenix
`identityPaths` point at `/persist` directly so decryption works before
impermanence bind-mounts. Manage with the devshell `agenix` command; recipient
config in `secrets.nix` (repo root).

## Hosts

- **sinnix-prime** — the workstation (i7-13700K, RTX 3080, 32G). GPU driver
  stack via single `sinnix.gpu.mode` toggle (nvidia/nvidia-open/igpu/dual).
  Ephemeral btrfs root `@` (initrd rollback + pre-wipe snapshots), `/persist`
  bind-mounts, `@sinex` nodatacow subvol for Postgres, `/realm` NVMe data
  volume. Journald capped 4G persistent (OOM forensics). fTPM broken →
  systemd-tpm2-setup masked.
- **sinnix-ethereal** — Hetzner AX42 headless replica
  (`profiles/cloud.nix`, disko, bootstrap via `nix run .#deploy-ethereal`,
  steady-state via colmena `apply-all`). Runs sinex `deploymentRole =
  "replica"` (postgres+NATS for remote thin workstations, no local capture).
- **sinnix-gw** — OpenWrt router, config generated from
  `hosts/sinnix-gw/default.nix` and pushed over SSH:
  `nix run .#router-deploy` (backup → opkg → UCI → health check).

## Storage & Wear Invariants

- Root MX500 is wear-limited: build scratch belongs on `/var/cache/nix-build`
  (chattr +C, deliberate), heavy repo scratch on `/realm/tmp/`, agent worktrees
  on `/realm/worktrees/`, DB-shaped workloads on nodatacow subvols (`@sinex`,
  `/realm/state/*`). Do not add write-heavy paths to `/` or `/persist` casually.
- Persistence is declared next to the owning module via
  `sinnix.persistence.{system,home}.{directories,files}`; anything not
  declared is wiped on reboot. New service state ⇒ add a persistence entry in
  the same change.
- Backups: btrbk snapshots (producer) are deleted only after the hourly Borg
  drain proves a matching archive on `/outer-realm` (durability gate). Status
  JSONL: `/realm/data/captures/machine/borg_status.jsonl`.

## Verification & Checks

- Applying config: `switch` (devshell) or `nix develop --command switch`.
  Risky changes: `test-vm` first, or `boot` + reboot. All rebuild paths share
  one lock, nix-build.slice containment, and a memory preflight
  (`SINNIX_REBUILD_SKIP_PRESSURE_PREFLIGHT=1` to override deliberately).
- `check` = curated default tier (cheap; `nix flake check` traversal has
  wedged this host — don't run it raw). `check-all` adds the heavy tier
  (`heavyChecks` flake output: HM runtime checks, VM checks, host builds).
  `lint` = deadnix/statix/shellcheck. `smoke [terminal|services|all]` = live
  host probes.
- **Live-drift tripwire:** `nixos-version --configuration-revision` reports
  the sinnix commit the running generation was built from
  (`system.configurationRevision` stamped in `flake/nixos.nix`; a `-dirty`
  suffix means uncommitted tree state was included). If it isn't repo HEAD,
  recent commits (and boot-time options like `boot.tmp.*`) are not live yet —
  say so instead of assuming config == reality. Plain `--revision` reports
  the NIXPKGS revision — an equally plausible-looking sha; do not read it as
  a sinnix commit. Generations older than 2026-07-10 predate the stamp and
  print nothing for `--configuration-revision`.

## Maintenance Protocol

- Update this file in the same commit when adding/removing/moving modules,
  changing conventions, or establishing patterns. Do not keep a changelog
  here — git history and Beads are the record.
- Keep guidance needed on most turns here; move specialized long-form
  procedure into skills (`dots/_ai/skills/`).
- After structural changes: focused test for the edited surface, then
  `switch` when the user wants the live system updated; spot-check the
  affected service/feature.
