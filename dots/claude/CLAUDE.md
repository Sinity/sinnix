# Base rules

- Task is not done until you ensure things compile, are commited, and there's no outdated documentation, especially your own memory. Update information in your memory whenever things change.
- Do not "solve" issues by turning off, removing, commenting out features. This does not count as solving.
- IMPORTANT: Do not remove files that couldn't later be recoverd via version control. That includes issuing git commands which would wipe them out. DO NOT use git restore on entire folders.
- Documentation, including comment, must always describe current reality on its own / standalone; never reference what was removed or changed. Just remove or change it.
  - Don't add comments which restate what you're doing. Make sure any comments you make, are meaningful outside your immediate context, with regards to entire codebase.
  - When making change in code or configuration simply do that change without adding any comments "acknowledging" what you're doing, speaking to me - this is bad because you're working on code which is not ephemeral. Only add comments when they provide actionable information or warn about non-obvious behavior.
  - When you are modifying the code, overwrite instead of accreating. You can change things freely - changes can be reverted in case it's necessary. Prune obsolete stuff. Also, past does not exist: do not write comments which refer to previous state of the code and describe the change. Comments must describe the current state standalone.
- Save full compilation output into a file, compilation.log, don't pipe it directly to wc -l or head or anything like that, to avoid pointless recompilation when you need to analyze output any other way

# Other

- Prefer fd over find, rg over grep etc. because these are faster.
- Prefer singular folder names over plural ones.

# Nix

- Operating system is NixOS.
- Scripts you run or write must use #!/usr/bin/env bash instead of #!/bin/bash.
- Nix flake builds only include files tracked in git; untracked or unstaged files are invisible to the build
- SQLX cache files must be committed to git for Nix builds to work (Nix only sees tracked files)
- Do not prefix command with "nix develop --command" without reason to. Enter nix shell at the start.
# Communication

- Cut out all gratuitous flattery and sycophancy. "You are absolutely right to" repeated in every message is grating.
