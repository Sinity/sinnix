#!/usr/bin/env bash
set -euo pipefail

spec=$1
jq -e '
  .schema_version == "sinnix-agent-teams-pilot-v1"
  and .task.mutation_policy == "read_only"
  and (.task.corpus | length) >= 4
  and .runtime.model == "sonnet"
  and .runtime.effort == "high"
  and (.runtime.stop_conditions | length) >= 3
  and .arms.teams.workers == ["researcher-a", "researcher-b", "synthesizer"]
  and .arms.independent.workers == ["researcher-a", "researcher-b", "researcher-c", "coordinator"]
  and (.receipt_fields | index("wall_time_ms"))
  and (.receipt_fields | index("coordination_message_count"))
  and (.receipt_fields | index("blinded_score"))
  and (.blinded_rubric.dimensions | length) == 4
  and (.blinded_rubric.thresholds | keys | sort) == ["adopt", "narrow", "park"]
  and .decision.allowed == ["adopt", "narrow", "park"]
  and .decision.status == "pending_execution"
' "$spec" >/dev/null
echo 'agent teams pilot fixture passed'
