# Infrastructure and profile default audit

Audit scope for `sinnix-ow0.1`, using the pinned NixOS evaluation and the active Sinnix module tree. Values are classified as removable only when the evaluated upstream default is identical and the setting carries no local policy meaning.

| Area | Files reviewed | Classification | Result |
| --- | --- | --- | --- |
| Build containment | `modules/build-policy.nix`, `flake/data/runtime-defaults.nix` | Incident-derived policy | Retain `max-jobs = 1` and `cores = 16`; add eval assertions so a future override fails with the incident rationale. The build scratch path and cgroup placement remain explicit because they are local storage and containment policy. |
| Workstation resource posture | `modules/profiles/workstation.nix` | Measured workstation policy | Retain zram size, priority, sysctls, earlyoom policy, and slice budgets. These values are measured responses to recorded pressure incidents, not upstream defaults. Existing earlyoom assertions remain in place. |
| Headless profile | `modules/profiles/cloud.nix` | Host-shape policy | Retain networkd, firewall, serial console, qemu guest, and X server settings. They select the cloud deployment shape and are not redundant defaults. |
| Core platform | `modules/core.nix`, `modules/networking.nix`, `modules/storage.nix` | Mixed | Retain explicit security, networking, storage, and persistence values where they encode Sinnix host policy. No deletion is recorded without pinned option-default evidence. |
| Runtime and persistence | `modules/runtime.nix`, `modules/persistence.nix` | Contract assertions | Existing typed assertions protect duplicate units, suffix/kind mismatches, unknown classes, and persistence declarations. No source-text fossil checks were added. |

The pass deliberately records no speculative deletions. A future audit slice can remove a value only after capturing its evaluated default and proving that the generated host behavior is unchanged.
