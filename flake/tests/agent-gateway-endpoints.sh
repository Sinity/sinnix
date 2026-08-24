#!/usr/bin/env bash
# Endpoint-specific gateway contract check.
#
# Provably fails when: the prime host loses endpoint identity, a generated
# endpoint config stops carrying its scope, an approval preflight is omitted,
# runtime inventory collapses the two units, or principal filtering exposes an
# effectful observer verb.
set -euo pipefail

flake_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmp_root="$(mktemp -d)"
trap 'rm -rf "$tmp_root"' EXIT

config_ref="$flake_root#nixosConfigurations.sinnix-prime.config"
eval_json() {
  nix eval --impure --json "$config_ref.$1"
}

endpoints_json="$(eval_json 'sinnix.services.agent-gateway.endpoints')"
jq -e '
  keys == ["observer", "operator"] and
  .observer.enable and .operator.enable and
  .observer.principal == "observer" and
  .operator.principal == "operator" and
  .observer.tunnelId != .operator.tunnelId and
  .observer.runtimeKeyFile != .operator.runtimeKeyFile and
  .observer.healthPort != .operator.healthPort and
  (.observer.scope.projects | length) > 0 and
  (.operator.scope.projects | length) > 0 and
  .observer.scope.captures != .operator.scope.captures and
  (.observer.approvedManifestHash | type) == "string" and
  (.observer.approvedActionCatalogHash | type) == "string" and
  (.operator.approvedManifestHash | type) == "string" and
  (.operator.approvedActionCatalogHash | type) == "string"
' <<<"$endpoints_json" >/dev/null

service_json="$(eval_json 'sinnix.services.agent-gateway')"
jq -e 'has("tunnel") | not' <<<"$service_json" >/dev/null

etc_json="$(eval_json 'environment.etc')"
observer_config="$(jq -r '."sinnix/agent-gateway-observer.json".source' <<<"$etc_json")"
operator_config="$(jq -r '."sinnix/agent-gateway-operator.json".source' <<<"$etc_json")"
case "$observer_config" in
  *sinnix-agent-gateway-observer.json) ;;
  *) exit 1 ;;
esac
case "$operator_config" in
  *sinnix-agent-gateway-operator.json) ;;
  *) exit 1 ;;
esac
test "$observer_config" != "$operator_config"

units_json="$(eval_json 'home-manager.users.sinity.systemd.user.services')"
jq -e '
  (has("sinnix-agent-gateway-tunnel") | not) and
  ."sinnix-agent-gateway-observer".Unit.ConditionPathExists == "/run/agenix/openai-tunnel-runtime-key" and
  ."sinnix-agent-gateway-operator".Unit.ConditionPathExists == "/run/agenix/openai-tunnel-runtime-key-operator" and
  (."sinnix-agent-gateway-observer".Service.ExecStartPre | length) == 1 and
  (."sinnix-agent-gateway-operator".Service.ExecStartPre | length) == 1 and
  (."sinnix-agent-gateway-observer".Service.ExecStartPre[0] | contains("observer-approval-gate")) and
  (."sinnix-agent-gateway-operator".Service.ExecStartPre[0] | contains("operator-approval-gate")) and
  (."sinnix-agent-gateway-observer".Service.ExecStart | join(" ") | contains("127.0.0.1:3088")) and
  (."sinnix-agent-gateway-operator".Service.ExecStart | join(" ") | contains("127.0.0.1:3089")) and
  (."sinnix-agent-gateway-observer".Service.ExecStart | join(" ") | contains("tunnel_6a2eb972c3bc8191be437670f455ebd9")) and
  (."sinnix-agent-gateway-operator".Service.ExecStart | join(" ") | contains("tunnel_3f0d5d6c4f1b2a9e8d7c6b5a4f3e2d1c")) and
  ."sinnix-agent-gateway-observer".Service.ProtectSystem == "strict" and
  (."sinnix-agent-gateway-operator".Service.ProtectSystem // null) == null
' <<<"$units_json" >/dev/null

surfaces_json="$(eval_json 'sinnix.runtime.surfaces')"
jq -e '
  (has("agent-gateway-tunnel") | not) and
  ."agent-gateway-observer".unit == "sinnix-agent-gateway-observer.service" and
  ."agent-gateway-operator".unit == "sinnix-agent-gateway-operator.service" and
  ."agent-gateway-observer".activation.publicEndpoint == "127.0.0.1:3088" and
  ."agent-gateway-operator".activation.publicEndpoint == "127.0.0.1:3089" and
  ."agent-gateway-observer".unit != ."agent-gateway-operator".unit
' <<<"$surfaces_json" >/dev/null

gateway_observer="$tmp_root/observer-manifest.json"
gateway_operator="$tmp_root/operator-manifest.json"
catalog_observer="$tmp_root/observer-catalog.json"
catalog_operator="$tmp_root/operator-catalog.json"
mkdir -p "$tmp_root/home" "$tmp_root/state"
HOME="$tmp_root/home" XDG_STATE_HOME="$tmp_root/state" \
  nix run "$flake_root#sinnix-agent-gateway" -- --principal observer manifest >"$gateway_observer"
HOME="$tmp_root/home" XDG_STATE_HOME="$tmp_root/state" \
  nix run "$flake_root#sinnix-agent-gateway" -- --principal operator manifest >"$gateway_operator"
HOME="$tmp_root/home" XDG_STATE_HOME="$tmp_root/state" \
  nix run "$flake_root#sinnix-agent-gateway" -- --principal observer catalog-hash >"$catalog_observer"
HOME="$tmp_root/home" XDG_STATE_HOME="$tmp_root/state" \
  nix run "$flake_root#sinnix-agent-gateway" -- --principal operator catalog-hash >"$catalog_operator"

test "$(jq -r '.observer.approvedManifestHash' <<<"$endpoints_json")" = "$(jq -r '.sha256' "$gateway_observer")"
test "$(jq -r '.operator.approvedManifestHash' <<<"$endpoints_json")" = "$(jq -r '.sha256' "$gateway_operator")"
test "$(jq -r '.observer.approvedActionCatalogHash' <<<"$endpoints_json")" = "$(jq -r '.sha256' "$catalog_observer")"
test "$(jq -r '.operator.approvedActionCatalogHash' <<<"$endpoints_json")" = "$(jq -r '.sha256' "$catalog_operator")"

jq -e '
  ([.tools[].name] | sort) as $names |
  ($names | all(. as $name | ["catalog", "context", "events", "get", "query", "status", "wait"] | index($name))) and
  ($names | all(. as $name | ["change", "operate", "run"] | index($name) | not))
' "$gateway_observer" >/dev/null
jq -e '
  ([.tools[].name] | sort) == ["catalog", "change", "context", "events", "get", "operate", "query", "run", "status", "wait"]
' "$gateway_operator" >/dev/null

printf '%s\n' 'agent-gateway endpoint evaluation and principal manifest checks passed'
