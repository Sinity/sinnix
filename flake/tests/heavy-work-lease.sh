#!/usr/bin/env bash
set -euo pipefail

lease_bin="${1:?lease command required}"
fixture="$(mktemp -d)"
trap 'rm -rf "$fixture"' EXIT
export SINNIX_HEAVY_LEASE_STATE_DIR="$fixture/state"

"$lease_bin" --state-dir "$fixture/state" --project sinex --work-item reindex -- bash -c 'printf start >>"$1"; sleep 0.4; printf end >>"$1"' _ "$fixture/order" &
owner=$!
for _ in {1..40}; do [[ -f "$fixture/state/owner.json" ]] && break; sleep 0.01; done
if "$lease_bin" --state-dir "$fixture/state" --project sinnix --work-item test -- bash -c 'printf overlap >>"$1"' _ "$fixture/order"; then
  echo "contending heavy work overlapped" >&2
  exit 1
fi
"$lease_bin" --state-dir "$fixture/state" status | jq -e '.owner.project == "sinex"' >/dev/null
wait "$owner"
[[ "$(<"$fixture/order")" == startend ]]

"$lease_bin" --state-dir "$fixture/state" -- bash -c '"$1" --state-dir "$2" -- true' _ "$lease_bin" "$fixture/state"
printf '{"schema":"sinnix-heavy-lease-v1","owner":{"pid":999999,"proc_start":"x","cgroup":"/x"}}\n' >"$fixture/state/owner.json"
"$lease_bin" --state-dir "$fixture/state" reconcile | jq -e '.reconciled == true' >/dev/null
[[ ! -e "$fixture/state/owner.json" ]]
[[ "$(stat -c %a "$fixture/state")" == 700 ]]
[[ "$(stat -c %a "$fixture/state/audit.jsonl")" == 600 ]]
