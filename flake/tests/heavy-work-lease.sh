#!/usr/bin/env bash
set -euo pipefail

lease_bin="${1:?lease command required}"
fixture="$(mktemp -d)"
trap 'rm -rf "$fixture"' EXIT
export SINNIX_HEAVY_LEASE_STATE_DIR="$fixture/state"

"$lease_bin" --state-dir "$fixture/state" --project sinex --work-item reindex -- bash -c 'printf start >>"$1"; sleep 0.4; printf end >>"$1"' _ "$fixture/order" &
owner=$!
for _ in {1..40}; do
  [[ -f "$fixture/state/owner.json" ]] && break
  sleep 0.01
done
# Source-only work is outside the heavy lease and remains concurrent.
bash -c 'printf source >"$1"' _ "$fixture/source"
[[ "$(<"$fixture/source")" == source ]]
set +e
contention_output="$("$lease_bin" --state-dir "$fixture/state" --project sinnix --work-item test -- bash -c 'printf overlap >>"$1"' _ "$fixture/order" 2>&1)"
contention_status=$?
set -e
if [ "$contention_status" -eq 0 ]; then
  echo "contending heavy work overlapped" >&2
  exit 1
fi
[ "$contention_status" -eq 75 ]
grep -Fq 'BLOCKED' <<<"$contention_output"
grep -Fq 'nothing was built or activated' <<<"$contention_output"
"$lease_bin" --state-dir "$fixture/state" status | jq -e '.owner.project == "sinex"' >/dev/null
# status's exit code is the held/free signal gating callers (sinnix-preflight)
# branch on -- must be 0 while a live owner holds the lease.
"$lease_bin" --state-dir "$fixture/state" status >/dev/null
wait "$owner"
[[ "$(<"$fixture/order")" == startend ]]
# ...and nonzero once the owner has released it.
set +e
"$lease_bin" --state-dir "$fixture/state" status >/dev/null
status_after_release=$?
set -e
[ "$status_after_release" -ne 0 ]

# A cancelled bounded waiter must not acquire later or leave descendants.
"$lease_bin" --state-dir "$fixture/state" -- bash -c 'sleep 2' &
owner=$!
for _ in {1..40}; do
  [[ -f "$fixture/state/owner.json" ]] && break
  sleep 0.01
done
"$lease_bin" --state-dir "$fixture/state" --wait-seconds 10 -- bash -c 'touch "$1"' _ "$fixture/waiter-ran" &
waiter=$!
sleep 0.1
kill -TERM "$waiter"
wait "$waiter" 2>/dev/null || true
[[ ! -e "$fixture/waiter-ran" ]]
kill -TERM "$owner"
wait "$owner" 2>/dev/null || true
[[ ! -e "$fixture/state/owner.json" ]]

# Cancelling the owner reaps its process group, including daemon-like children.
"$lease_bin" --state-dir "$fixture/state" -- bash -c 'sleep 300 & printf "%s" "$!" >"$1"; wait' _ "$fixture/child.pid" &
owner=$!
for _ in {1..40}; do
  [[ -s "$fixture/child.pid" ]] && break
  sleep 0.01
done
child="$(<"$fixture/child.pid")"
kill -TERM "$owner"
wait "$owner" 2>/dev/null || true
if kill -0 "$child" 2>/dev/null; then
  echo "cancelled lease left descendant $child" >&2
  exit 1
fi

"$lease_bin" --state-dir "$fixture/state" -- bash -c '"$1" --state-dir "$2" -- true' _ "$lease_bin" "$fixture/state"
printf '{"schema":"sinnix-heavy-lease-v1","owner":{"pid":999999,"proc_start":"x","cgroup":"/x"}}\n' >"$fixture/state/owner.json"
"$lease_bin" --state-dir "$fixture/state" reconcile | jq -e '.reconciled == true' >/dev/null
[[ ! -e "$fixture/state/owner.json" ]]
[[ "$(stat -c %a "$fixture/state")" == 700 ]]
[[ "$(stat -c %a "$fixture/state/audit.jsonl")" == 600 ]]
