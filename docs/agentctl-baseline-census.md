# AgentCTL baseline census

This census freezes the execution surfaces and callers that the AgentCTL consolidation must account for. The machine-readable source is [agentctl-baseline-census.json](agentctl-baseline-census.json). A later deletion bead may close only against a surface ID from that file and must rerun its evidence command after migration.

The authority split is: systemd owns live process trees and cgroups; Git owns commits and worktrees; Beads owns task state; AgentCTL owns transient jobs, workspaces, agent launches, and service leases; project adapters own semantic setup, checks, and result parsing. The gateway, skills, and project CLIs are callers, not additional execution authorities.

The census covers Sinnix, Polylogue, Sinex, and Sinity Lynchpin source trees. It excludes Git metadata, build trees, runtime databases, and captured personal data. Search terms are recorded in the JSON so the census can be repeated without relying on this prose.

## Baseline measurements

The checked-in Sinnixd runtime contains 24 Python source files and 19,906 source lines. The gateway source set contains 27,220 lines and executable skill scripts contain 5,116 lines. These are source-size measurements, not deletion claims. The JSON records the exact file classes used for each count.

The child-tree lifecycle evidence exists in two scopes. The unit fixture enters a real user systemd manager and proves cgroup cancellation removes a shell parent and its background descendant. The `sinnixd-vm` fixture repeats the route through `agentctl job start`, `job cancel`, and `job wait`, then checks both recorded PIDs. It also exercises the shell and coding-agent contracts.

## Reproduction

Run the recorded search commands from the relevant repository roots. Run the verification commands through the owning managed operation. The VM check is intentionally separate from the unit test because only the VM proves the installed service and CLI route together.

The baseline has no deletion delta. Later waves must report added and deleted source lines and command-surface changes, and must reference the affected census IDs. A search result that is only historical documentation does not establish a live caller; a live caller must be classified by its source path and invocation recorded in the JSON.
