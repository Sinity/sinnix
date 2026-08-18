# Sinnix Configuration

> **Working contract for agents editing this repo** — the NixOS system
> configuration for `sinnix-prime` (workstation), `sinnix-ethereal` (Hetzner
> replica), and `sinnix-gw` (OpenWrt router). Single flat file, no
> transclusion; `AGENTS.md` is a committed symlink to this file. Update this
> file in the same commit as any structural change it describes.
>
> Deep architecture and machine maps live in `.agent/scratch/`
> (`*-sinnix-architecture-grok.md`, `*-machine-map.md`); both are dated
> 2026-07-07 and predate the 2026-08 reduction drive, so treat them as
> orientation, not current fact — this file and the tree win.

---

## Standing Rules

- Place new config by the module taxonomy below before writing it; check the
  existing script/skill registry before adding a helper.
- **No aliases, no transition periods.** A rename or replacement updates every
  reference in one pass; deprecated compatibility interfaces are never kept.
  Retired capabilities leave the active tree entirely — git history is the
  archive, and comments/docs describe the present design without narrating
  what it replaced.
- **`switch` is self-verifying** — it evaluates and builds before activating.
  Never wrap it in hygiene probes (`check --no-build` first, standalone
  `nix eval`/`nix build` on config edits): they are slow on this host and
  repeat work `switch` performs through the intended resource wrapper. If
  `switch` fails during activation, fix the blocker and rerun `switch`.
- **Beads (`bd`) is the work tracker.** `bd prime` for context; discovered
  follow-ups become linked issues, not markdown TODO lists. `bd dolt push`
  follows the same policy as `git push`: verified `master` work may be pushed
  directly; explicit hold instructions are never bypassed.

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
- Before every commit, review the complete staged diff for private prose,
  fixtures, identifiers, and datasets. Known private path and file shapes are
  blocked by `.gitignore`; no script can judge content — that review is the
  committer's job. When in doubt whether content belongs in the public repo,
  confirm with the operator before committing it.
- Publish only `master`. Never push `--mirror`, `--all`, or `--tags`; any new
  branch or tag requires an explicit publication review first.
- If private material was committed, stop publication, rotate any live secret,
  rewrite the allowed branch, and verify a fresh clone. Deleting the current
  file does not remove it from history.

## Architecture Map

Evaluation pipeline: `flake.nix` (flake-parts) → `flake/nixos.nix` `mkHost` →
`flake/lib-context.nix`, which builds the extended lib (`lib.sinnix.*`) and
`specialArgs`:

- `mkFeatureModule` / `mkServiceModule` — module factories
  (`modules/lib/features.nix`), injected directly into specialArgs.
- `helpers.data` — pure data tables from `flake/data/` (`mcpRegistry`,
  `runtimeDefaults`, `localModels`, `agentLanes`), evaluated once at flake
  init and shared by reference. Modules consume them via specialArgs; never
  re-`import` the data files.
- `helpers.mkSinnixPackagesFor pkgs` — the script package set (see Scripts).
- `lib.sinnix` — factory helpers, `systemd` hardening helpers,
  `mkRuntimeServiceConfig`, `mkAutoImports`, overlay helpers.

`modules/default.nix` auto-imports every module via
`lib.sinnix.mkAutoImports ./. [ "lib" ]` — new modules need zero wiring.

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
  `build-policy.nix` (nix daemon: max-jobs=4/cores=16, build scratch at
  `/var/cache/nix-build`), `runtime.nix` (runtime inventory — see below),
  `persistence.nix` (impermanence collector), `backup.nix` (btrbk→Borg
  pipeline), `secrets.nix` (agenix auto-discovery), `dotfiles-sweep.nix`,
  `introspection.nix` (`/etc/sinnix/config.json`). Desktop resource
  governance (slices, sysctls, earlyoom, io.cost init) lives in
  `profiles/workstation.nix`, not a top-level module.

## Factory Contracts

- **Features are default-ON.** `mkFeatureModule` sets `enable.default = true`:
  anything in `modules/features/` is unconditionally part of a sinnix host's
  default character. Hosts express _exceptions_
  (`sinnix.features.<path>.enable = false`) and configuration detail, not
  enables. Optional background capabilities belong in the default-off service
  namespace.
- **Services are default-OFF.** `mkServiceModule { name, surface, ... }`
  creates `sinnix.services.<name>`; hosts opt in. The optional `surface`
  argument auto-registers the unit in `sinnix.runtime.surfaces` so resource
  governance is co-located with the declaration.
- **AI backends use a third factory.** `mkAiService { name, description, unit,
endpoint, activation, backendKind, requiresCuda, ... }` wraps
  `mkServiceModule` and additionally builds the surface, the socket-proxy
  activation, and the `meta.ai` block. Used by `stt`, `tts`, `kokoro`,
  `open-webui`. Reach for it for anything that is a model endpoint; reach for
  `mkServiceModule` for everything else.
- **Every scheduled oneshot renders through one renderer**,
  `lib.sinnix.mkScheduledJob` (`modules/lib/scheduled-job.nix` — the spec-key
  reference lives in its header: execStart or script, timer, manager,
  resourceClass for user-manager jobs, serviceConfig/unit passthroughs).
  Single-job service modules use the factory's `job` argument, which is sugar
  over it (adds unitName defaulting to sinnix-<name>); multi-job services
  (steering), feature modules, and infrastructure modules call it directly in
  their config (`runtime.nix`'s config-drift, `diagnostics.nix`'s three,
  `backup.nix`'s eleven through one local `mkBackupJob`). No hand-written
  systemd.services/timers pairs and no HM-format user units for scheduled
  jobs; the one exception is mi-unlock's deadline-waiting simple service.
  `surface` and `job` may be attrsets or functions of the module args
  (function form: the module FILE must name `pkgs` in its own pattern for a
  job that uses it — \_module.args inject only named formals). A
  system-manager job resolves its resource class from the unit's registered
  surface, so the surface comes first; pass that surface to the renderer so
  failure-notify is not attached twice.
- **Capture lanes use `mkCaptureLane`** (`modules/lib/capture-lane.nix`,
  composed as `mkServiceModule (mkCaptureLane { ... }) args`): poll and
  stream modes, lane/tmpfiles/captures/surface synthesis, shared hardening.
  The five non-fitting capture modules are enumerated in its header.
- **Failure reporting is a property of registration.** One template,
  `sinnix-unit-failure-notify@` (system + user twins, one body, declared in
  runtime.nix), auto-attached to every observed surface and every generated
  job. Never hand-wire a second failure-notify mechanism.
- `pkgs/sinnix-lib` (python module `sinnix_lib`) is the shared library:
  atomic_json, ledger + the one receipt schema, flock, notify, systemd show
  parser, spool (durable inbox, exactly-once). Python packages depend on
  it; never re-implement these helpers.
- `subFeatures = { x = { description; default; }; ... }` generates nested
  `<feature>.x.enable` toggles (see `features/dev/shell.nix`).
- `meta.dotfiles.{configFile,dataFile,homeFile}` entries are collected by
  `modules/dotfiles-sweep.nix` into HM out-of-store symlinks pointing at
  `dots/<rel>`. String value ⇒ simple symlink; attrset ⇒
  `{ source; recursive; force; }`.
- **Modules that use no factory — the complete list.** A factory bypass is a
  cost every reader pays, so the set is enumerated here and adding to it needs
  a reason of the same shape as these:
  - `features/desktop/hyprland/` — multi-file, tightly coupled system+HM
    config. Reserve that shape for WM-level complexity.
  - `services/ml-containers.nix` — shared container _runtime_ (podman storage,
    CDI, digest pinning) that the AI services depend on; it configures a
    substrate rather than owning a unit.
  - `services/sinex.nix` + `services/sinex/bridge.nix` — glue onto an upstream
    flake's own `services.sinex` module, so the option surface is upstream's
    to shape, not `mkServiceModule`'s.
  - `services/ai-control.nix` — installs `scripts/sinnix-ai`, which carries the
    service registry itself; there is no unit here to declare.
  - `services/capture-registry.nix` — declares `sinnix.runtime.captures`
    entries for lanes with no owning unit. Not a service at all.
  - `features/dev/agents/*.nix` except `clis.nix` and `mcp.nix` — plain-Nix
    helpers imported directly by those two, not auto-imported modules.

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
  units, kind/suffix mismatches, and unknown classes. `kind` is always a real
  systemd unit type and `unit` always ends in it — there is no exemption.
- A capture lane whose writer is **not** a unit (a hotkey script, a shell
  wrapper) goes in `sinnix.runtime.captures` instead: same lane fields, no
  `unit`. Both sources flatten into one `.captures` array in the inventory, so
  the health sweep and every other consumer see one kind of lane. Do not
  invent a synthetic unit name to fit a lane into a surface — that is what
  this option exists to prevent.
- `lib.sinnix.mkRuntimeServiceConfig { runtimeInventory; unit; }` resolves a
  unit to its class serviceConfig (as mkDefault) and **throws on unknown
  units** — register the surface first.
- The whole inventory is serialized to `/etc/sinnix/runtime-inventory.json`,
  consumed at runtime by `sinnix-observe`, machine telemetry, and the
  ops-reducer's health sweep — the inventory-driven check (lane staleness,
  payload degeneracy, liveness probes, mount capacity, unit resting state)
  that runs on the reducer's own 60s tick inside the operator's session,
  writes `sinnix-health-transition-v1` lines to
  `/run/sinnix/health-transitions.jsonl`, notifies the desktop, and shares
  one dedup state with the `sinnix-unit-failure-notify@` OnFailure path.
  When adding a daemon: declare the surface, apply `mkRuntimeServiceConfig`,
  done — no ad-hoc Nice/IOWeight overrides.
- **Launch policy is rendered, not interpreted.** `flake/launch.nix` generates
  the `sinnix-scope` launcher from `commandClasses`: one `apply_class_policy`
  shell function whose branches carry the baked slice, nice/ionice, systemd
  properties and env defaults, prepended to the runtime half in
  `flake/launch/scope-runtime.bash` (argument parsing, cgroup checks,
  unit-name synthesis, the scope supervisor). `renderDirenvrc` does the same
  for the devshell command wrappers' class resolver. Nothing reads
  `/etc/sinnix/runtime-inventory.json` to _place_ a process — the inventory
  carries `commandClasses` for observability only. A class that is not in the
  table is a usage error naming the classes that are; adding one is a table
  edit, not a launcher edit.
- Concurrency is governed by slice memory caps and weights, not
  serialization; the only build-path lock is `/tmp/sinnix-switch.lock`, a
  correctness guard against two activations racing on the system profile.
  Gateway and native launches share versioned UUID manifests and correlation
  IDs consumed by `sinnix-observe`.

## Flake Layout & Input Pinning

`flake/`: `nixos.nix` (hosts), `lib-context.nix` (shared bootstrap),
`dev-shell.nix` + `command-registry.nix` (rebuild commands — single source of
truth for lock/containment/preflight shared by devshell binaries and
`nix run .#switch`), `scripts.nix` + `script-discovery.nix` (script registry),
`launch.nix` + `launch/scope-runtime.bash` (the generated `sinnix-scope`
launcher — see Runtime Governance), `packages.nix` (public package surface),
`tests.nix` + `tests-runtime.nix` + `test-lib.nix` + `tests/*.{nix,sh}` (the
individual checks), `router.nix` (sinnix-gw), `deploy.nix` (colmena +
nixos-anywhere), `overlay/package/*.nix` (per-package overlays),
`data/*.nix` (pure data: MCP registry, runtime defaults, local model roster,
shared skill list, agent CLI wrapper lane registry).

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
  compiled at most once. The desktop is the builder of record — nothing in
  sinex CI publishes to sinity.cachix.org — and `switch` publishes the sinex
  closure to the cache after a successful activation (`sinexCachePush`,
  flake/command-registry.nix, backed by the shared
  `scripts/sinnix-sinex-cache-push` push logic). The FIRST switch after a
  sinex master bump doesn't pay that compile synchronously:
  `sinnix.services.sinex-cache-prebuild` (enabled on sinnix-prime) is a
  periodic timer that diffs flake.lock's sinex revision against a state
  file, and on a move builds + cache-pushes it async under
  `sinnix-scope nix-build` (sinnix-m9v).
- `lynchpin` and `steering` are local `git+file://` inputs;
  sinex/polylogue/scribe-tap/yt-polisher/phone-app come from GitHub so
  deploys don't consume local checkout state. One-off local testing:
  `SINNIX_{SINEX,POLYLOGUE,LYNCHPIN}_OVERRIDE=<path> switch` (wired as
  `--override-input --no-write-lock-file`).

## Notable Services & Packages

Surfaces with standing design decisions an agent might otherwise "fix":

- `sinnix.services.stt` (`modules/services/stt.nix`, `scripts/sinnix-stt`,
  docs/speech.md) is the system's speech stack, served OpenAI-compatible at
  `/v1/audio/transcriptions`. Four sherpa-onnx models under
  `/realm/library/models/sherpa`, fetched on first start: Parakeet TDT 0.6B v3
  (int8) transcribes, Silero VAD gates, pyannote segmentation 3.0 diarizes,
  and NeMo TitaNet-small embeds speakers for verification. It is **CPU-only
  and deliberately outside the `gpu-inference` admission mesh**: fast enough
  on CPU (RTF ~0.1 on dense speech) that transcription never queues behind a
  resident model. Do not "fix" that by adding CUDA or the admission key; the
  runtime test asserts it stays out of the mesh.
- `sinnix.services.muse-glimmer` (`modules/services/muse-glimmer.nix`) serves
  the official Muse Glimmer 30B Q4 GGUF directly through llama.cpp:
  socket-activated, GPU-exclusive hybrid CPU/GPU, 1536 MiB fit margin, 32K
  single-slot context. Deliberately separate from both the Ollama roster and
  the llama.cpp reranker because the current Ollama package does not load
  Glimmer's architecture. Its CUDA llama.cpp package is pinned to upstream
  b10353 until nixpkgs-ai carries that support; LiteLLM exposes the endpoint
  as `local-glimmer`.
- The phone app (Sinnix, `dev.sinnix.phone`) lives in its own repo,
  github:Sinity/sinnix-phone-app, consumed as the non-flake `phone-app`
  input. Kotlin/Compose built through Gradle against a license-accepting
  re-import of the same nixpkgs, made reproducible by the nixpkgs Gradle
  setup hook plus a committed `deps.json` recorded through `mitm-cache`;
  regenerate with the derivation's `mitmCache.updateScript` after any
  dependency change. The APK is emitted unsigned and signed at install time
  against a persistent host-local keystore, which keeps `adb install -r` an
  upgrade rather than an uninstall that discards runtime grants. Prime's
  counterpart is `pkgs/sinnix-phone-dispatcher`, served at the hub's
  `/phone/v1/*`: the app pushes everything it produces and fetches
  everything prime has for it, so there is no scheduled drain and
  `sinnix.services.phone-logcat` is all that pulls (the system log needs
  READ_LOGS, which the app cannot hold). Operate it through
  `sinnix phone app-*`; lane detail in `docs/phone.md`.

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
non-script externals (lynchpin/polylogue/steering pythons, vendored npm CLIs,
beads); `flake/packages.nix` curates the small public `nix run` surface.
`sinnix` (`flake/cli-dispatcher.nix`, installed by
`modules/features/cli/core.nix`) is a generated meta-CLI front door over the
whole packaged registry: `sinnix help` lists every script, `sinnix <name>`
dispatches to it (short name or full `sinnix-<name>`) — it needs zero wiring
when a new script is added.

## Dotfiles & Agent Context

- Everything in `dots/` reaches `$HOME` via HM out-of-store symlinks
  (`mkDotsFileFor` or `meta.dotfiles`) — edits propagate instantly, no
  rebuild. Claude Code settings are split (tested invariant): durable policy
  (hooks, permissions, env) lives in `dots/claude/managed-settings.json`,
  deployed as a symlink at `/etc/claude-code/managed-settings.json`;
  `~/.config/claude/settings.json` is a plain writable file seeded once from
  `dots/claude/settings-seed.json` so harness UI writes (model, effort,
  plugin toggles) never dirty the repo. Never manage either through HM store
  files.
- `dots/claude/CLAUDE.md` is the **global** agent instruction file (flat, no
  transclusion). `~/.codex/AGENTS.md` and `~/.gemini/GEMINI.md` are symlinks
  to it via `~/.config/claude/CLAUDE.md`. There is no render pipeline.
- Repo convention across the constellation: per-repo `CLAUDE.md` is canonical
  and flat; `AGENTS.md` is a committed symlink to it.
- Shared skills live in `dots/_ai/skills/`; agent trees (`~/.config/claude/
skills`, `~/.codex/skills`, `~/.gemini/skills`) are linkFarms over it.
  Codex-only system skills: `dots/codex/skills/.system/`.
- Agent CLI / MCP data lives in `flake/data/`: `mcp-registry.nix` (servers,
  tiers, lean/evidence/full/browser profiles, per-client render) and
  `agent-lanes.nix` (`helpers.data.agentLanes` — the per-client/backend
  variant axis: which MCP tier, which model/backend, which key source;
  hermes profiles, claude/codex full/lean/browser/deepseek/local lanes).
- Wiring lives in `modules/features/dev/agents/`. `clis.nix`
  (`sinnix.features.dev.agentTools`) renders the lane registry into CLI
  wrappers (npm-bootstrapped into `~/.local/state/<agent>/npm`,
  self-updating; `claude` aliases `claude-lean` because the upstream
  installer clobbers the bare path); `backends.nix` supplies the shared
  backend-env builders (`mkClaudeBackendEnv`/`mkCodexBackendEnv`) the
  deepseek/local lanes parameterize. `mcp.nix`
  (`sinnix.features.dev.mcp-servers`) plus `mcp-tools.nix`/
  `client-profiles.nix`/`serena.nix`/`browser.nix`/`hooks.nix` own the MCP
  registry wiring and per-client (Codex/Gemini) config generation. Only
  `clis.nix`/`mcp.nix` are real NixOS modules; the sibling files are
  plain-nix helpers imported directly, not auto-imported.
- Agent gateway: `modules/services/agent-gateway.nix` renders one canonical
  project contract and one official-SDK stdio MCP implementation with
  `remote-readonly`, `local-agent-control`, and `remote-operator` profiles.
  `sinnix-agent-control-mcp` is a thin local wrapper around that
  implementation. Remote ChatGPT access uses the pinned OpenAI
  `tunnel-client` user service; the gateway has no custom HTTP/SSE transport
  or separate PID job substrate.

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
  systemd-tpm2-setup masked. `sinnix.services.hub`
  (`modules/services/hub.nix`, docs/hub.md) is the browser front door:
  Caddy in the user manager serving `/reports/` off disk and proxying every
  other path to the ops-reducer, which renders every hub page on request
  from state it already holds — the system dashboard, `/work/` (semantic
  workload view over scopes, the project ledger and gateway jobs),
  `/services/`, `/ai/`, `/shaders/` — and whose buttons post to that same
  reducer's bounded action API. No second control plane: where the action
  API cannot express a target the page says so rather than growing a private
  kill path — `/shaders/` is entirely buttonless for exactly that reason,
  since applying a screen shader is not an action verb. It binds loopback
  plus the tailscale0 address via an explicit Caddy `bind` (site addresses
  alone collapse to a `:PORT` wildcard) and opens its ports on tailscale0
  only.
- **sinnix-ethereal** — Hetzner AX42 headless replica
  (`profiles/cloud.nix`, disko, bootstrap via `nix run .#deploy-ethereal`,
  steady-state via colmena `apply-all`). Runs sinex `deploymentRole =
"replica"` (postgres+NATS for remote thin workstations, no local capture).
  **Status: placeholder** (operator, 2026-08-12) — the multi-host future it
  represents hasn't arrived; do not design against it as a load-bearing
  target (backup destination, always-on substrate, etc.) without an explicit
  operator decision. Keep its config compiling; don't grow its role.
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
  drain proves a matching archive on `/outer-realm` (durability gate).
  `/realm/state` roots that snapshots cannot cover (nested subvols snapshot
  as empty directories) get direct-path Borg jobs instead; live SQLite
  databases are covered by dump units (`sinnix-sqlite-backup`), never
  file-copied mid-write, and large near-static derived artifacts ride Borg
  dedup rather than the dump path. Borg freshness (archive markers,
  snapshot-queue lag, integrity-receipt state) is watched as ops-reducer
  health lanes declared on the owning surfaces in `modules/backup.nix`, not
  a bespoke checker; drill evidence still lands in `borg_drill.jsonl`.
- **Backup membership is a property the directory carries, not a path in a
  list.** A directory is excluded when it holds `CACHEDIR.TAG` (the
  bford.info standard, which cargo/uv/ruff/pytest/mypy write unprompted) or
  `.nobackup` (sinnix's marker for regenerable scratch that is not a cache);
  `borg create` honours both via `--exclude-caches` / `--exclude-if-present`.
  Untagged means kept, so an unclassified new dataset is over-preserved
  rather than silently lost. **Mark new caches; do not extend
  `realmExcludes`** — that list is now only a safety net for things that
  cannot self-describe (`node_modules`, an untagged `target`). Path rules
  silently stop applying the moment something is named unexpectedly:
  `"cache"` matched only `/realm/cache` while `data/self/genome/cache` put
  285G of public reference downloads into every archive for months, and
  `.lynchpin/cache` and `.sinex/trybuild-target` slipped past for the same
  reason.
- Three preservation classes decide the marker. **Irreplaceable** (raw
  captures, sequencing reads) and **expensive-derived** — regenerable in
  principle but it cost money or many hours, e.g. paid cloud compute — both
  stay unmarked and backed up. Only **true cache**, re-acquired seamlessly
  and free when missing, gets a marker; a directory called cache that does
  not regenerate seamlessly is misfiled, and the fix is to make it seamless
  or reclassify it. `sinnix-cache-audit` lists large directories with their
  marker state (`--dry-run` asks borg itself, which is authoritative); run it
  with sudo, since unreadable paths make every size a lower bound.

## Verification & Checks

- Applying config: `switch` (devshell) or `nix develop --command switch`.
  Risky changes: `test-vm` first, or `boot` + reboot. All rebuild paths share
  one lock, nix-build.slice containment, and the read-only
  `sinnix-preflight switch` gate. Reboot inspection uses
  `sinnix-preflight reboot`; `SINNIX_PREFLIGHT_FORCE=1` is a deliberate,
  explicit override. The preflight checks only things it can actually know:
  nix free space, a concurrent generation operation, generation pairing,
  flake drift. It deliberately does NOT gate on memory headroom — a fixed
  MemAvailable threshold cannot tell a no-op rebuild from a world rebuild,
  and build memory is already bounded while it runs by nix-build.slice
  rather than guessed at before it starts.
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
  a sinnix commit.
- **A switch's exit code is not evidence it applied.** `sinnix-preflight`
  can BLOCK a switch (exit 75) for any of its gate reasons above — this is
  correct behaviour, and it means "I ran switch" and "the system changed"
  are different claims. Shell shapes like `switch > log; echo $?; tail log`
  report the exit status of the LAST command, so a blocked switch reads as
  success; the same applies to any harness that reports a compound command's
  status. The revision comparison above is the only check that settles it,
  so make it after every switch rather than trusting a 0. This is not
  hypothetical: switches have been reported applied while the system stayed
  on an older generation.

## Maintenance Protocol

- Update this file in the same commit when adding/removing/moving modules,
  changing conventions, or establishing patterns. No changelog here — git
  history and Beads are the record.
- Keep guidance needed on most turns here; move specialized long-form
  procedure into skills (`dots/_ai/skills/`).
- After structural changes: focused test for the edited surface, then
  `switch` when the user wants the live system updated; spot-check the
  affected service/feature.
