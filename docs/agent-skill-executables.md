# Agent skill executable ownership

This audit records every executable beneath `dots/_ai/skills`. AgentCTL is the only retained lifecycle owner. The allowed native runner is a private argv translator called by Sinnixd; no skill executable owns job state, cancellation, retries, manifests, or process cleanup.

| Executable | Positive caller | Retained role |
| --- | --- | --- |
| `orchestrate/scripts/build_plan_batch_prompts.py` | `orchestrate` skill | Writes operator-reviewed prompt files only. |
| `orchestrate/scripts/probe_agent_runtime.sh` | `orchestrate` skill and runtime-modes reference | Direct vendor and quota availability probe. |
| `agent-runtime/scripts/run_agent_prompt.sh` | Sinnixd service contract | Private backend argv translator for an attested job. |
| `chatgpt-conversations/scripts/sinnix-chatgpt-conversations` | `chatgpt-conversations` skill | Read-only conversation extraction from the shared browser. |
| `desktop-control-plane/scripts/chrome-control.sh` | Agent module and desktop-control-plane skill | Visible browser UI helper. |
| `desktop-control-plane/scripts/hypr-control.sh` | Agent module and desktop-control-plane skill | Visible window-manager UI helper. |
| `desktop-control-plane/scripts/keyboard-control.sh` | Agent module | Explicit keyboard UI helper. |
| `desktop-control-plane/scripts/kitty-remote-control.sh` | Agent module and desktop-control-plane skill | Visible terminal UI helper. |
| `desktop-control-plane/scripts/screenshot-color-lab.sh` | Agent module and capture registry | Screenshot and display diagnostic helper. |
| `grok/scripts/partition_by_size.sh` | `grok` skill | Measured source partitioning for a code audit. |
| `html-report/generators/embed-path-popups.py` | `html-report` skill | HTML report navigation generator. |
| `investigate/scripts/freeze.sh` | `investigate` skill | Evidence preservation before recovery mutation. |
| `investigate/scripts/recover-probe.sh` | `investigate` skill | Read-only recovery authority probe. |
| `skill-authoring/scripts/validate_skill.py` | `skill-authoring` skill and agent-tools check | Skill metadata and structure validation. |
