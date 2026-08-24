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
  .observer.enable and (.operator.enable | not) and
  .observer.principal == "observer" and
  .operator.principal == "operator" and
  .observer.healthPort != .operator.healthPort and
  (.observer.scope.projects | length) > 0 and
  (.operator.scope.projects | length) > 0 and
  .observer.scope.captures != .operator.scope.captures and
  (.observer.approvedManifestHash | type) == "string" and
  (.observer.approvedActionCatalogHash | type) == "string"
' <<<"$endpoints_json" >/dev/null

dual_endpoints_json="$(nix eval --impure --json --expr "
  let
    flake = builtins.getFlake \"$flake_root\";
    base = flake.nixosConfigurations.sinnix-prime;
    dual = base.extendModules { modules = [ ({ lib, ... }: {
      sinnix.services.agent-gateway.endpoints.operator = {
        enable = lib.mkForce true;
        tunnelId = \"tunnel-test-operator\";
        runtimeKeyFile = \"/run/test/operator-runtime-key\";
        approvedManifestHash = \"test-operator-manifest\";
        approvedActionCatalogHash = \"test-operator-catalog\";
      };
    }) ]; };
    agentControlConfig = dual.config.environment.etc.\"sinnix/agent-gateway.json\".source;
    observerConfig = dual.config.environment.etc.\"sinnix/agent-gateway-observer.json\".source;
    operatorConfig = dual.config.environment.etc.\"sinnix/agent-gateway-operator.json\".source;
  in {
    services = dual.config.home-manager.users.sinity.systemd.user.services;
    surfaces = dual.config.sinnix.runtime.surfaces;
    configs = {
      agentControl = { output = toString agentControlConfig; derivation = agentControlConfig.drvPath; };
      observer = { output = toString observerConfig; derivation = observerConfig.drvPath; };
      operator = { output = toString operatorConfig; derivation = operatorConfig.drvPath; };
    };
  }
")"
jq -e '
  .services | has("sinnix-agent-gateway-observer") and
  has("sinnix-agent-gateway-operator") and
  ."sinnix-agent-gateway-observer".Service.ExecStart !=
    ."sinnix-agent-gateway-operator".Service.ExecStart
' <<<"$dual_endpoints_json" >/dev/null
jq -e '
  .surfaces."agent-gateway-observer".unit == "sinnix-agent-gateway-observer.service" and
  .surfaces."agent-gateway-operator".unit == "sinnix-agent-gateway-operator.service" and
  .surfaces."agent-gateway-observer".activation.publicEndpoint !=
    .surfaces."agent-gateway-operator".activation.publicEndpoint
' <<<"$dual_endpoints_json" >/dev/null

service_json="$(eval_json 'sinnix.services.agent-gateway')"
jq -e 'has("tunnel") | not' <<<"$service_json" >/dev/null

etc_json="$(eval_json 'environment.etc')"
observer_config="$(jq -r '."sinnix/agent-gateway-observer.json".source' <<<"$etc_json")"
test "$(jq 'has("sinnix/agent-gateway.json")' <<<"$etc_json")" = true
case "$observer_config" in
  *sinnix-agent-gateway-observer.json) ;;
  *) exit 1 ;;
esac
test "$(jq 'has("sinnix/agent-gateway-operator.json")' <<<"$etc_json")" = false

agent_control_config="$(jq -r '.configs.agentControl.output' <<<"$dual_endpoints_json")"
dual_observer_config="$(jq -r '.configs.observer.output' <<<"$dual_endpoints_json")"
dual_operator_config="$(jq -r '.configs.operator.output' <<<"$dual_endpoints_json")"
case "$dual_observer_config" in
  *sinnix-agent-gateway-observer.json) ;;
  *) exit 1 ;;
esac
case "$dual_operator_config" in
  *sinnix-agent-gateway-operator.json) ;;
  *) exit 1 ;;
esac
case "$agent_control_config" in
  *sinnix-agent-gateway.json) ;;
  *) exit 1 ;;
esac
test "$dual_observer_config" != "$dual_operator_config"
nix-store --realise \
  "$(jq -r '.configs.agentControl.derivation' <<<"$dual_endpoints_json")" \
  "$(jq -r '.configs.observer.derivation' <<<"$dual_endpoints_json")" \
  "$(jq -r '.configs.operator.derivation' <<<"$dual_endpoints_json")" >/dev/null
jq -e '
  .endpoint.name == "agent-control" and
  .endpoint.principal == "agent-control" and
  (.projects | length) > 0 and
  (.captureCommand | endswith("/bin/sinnix-capture"))
' "$agent_control_config" >/dev/null
jq -e '
  .approvedManifestPrincipal == "observer" and
  .endpoint.principal == "observer" and
  (.endpoint.scope.projects | length) > 0
' "$dual_observer_config" >/dev/null
jq -e '
  .approvedManifestPrincipal == "operator" and
  .endpoint.principal == "operator" and
  (.endpoint.scope.projects | length) > 0
' "$dual_operator_config" >/dev/null

units_json="$(eval_json 'home-manager.users.sinity.systemd.user.services')"
jq -e '
  (has("sinnix-agent-gateway-tunnel") | not) and
  ."sinnix-agent-gateway-observer".Unit.ConditionPathExists == "/run/agenix/openai-tunnel-runtime-key" and
  (."sinnix-agent-gateway-observer".Service.ExecStartPre | length) == 2 and
  (."sinnix-agent-gateway-observer".Service.ExecStartPre[0] | contains("observer-state-scaffold")) and
  (."sinnix-agent-gateway-observer".Service.ExecStartPre[1] | contains("observer-approval-gate")) and
  ."sinnix-agent-gateway-observer".Service.ReadWritePaths == ["-/home/sinity/.local/state/sinnix/agent-gateway/observer"] and
  (."sinnix-agent-gateway-observer".Service.ExecStart | join(" ") | contains("127.0.0.1:3088")) and
  (."sinnix-agent-gateway-observer".Service.ExecStart | join(" ") | contains("tunnel_6a2eb972c3bc8191be437670f455ebd9")) and
  ."sinnix-agent-gateway-observer".Service.ProtectSystem == "strict" and
  (has("sinnix-agent-gateway-operator") | not)
' <<<"$units_json" >/dev/null

surfaces_json="$(eval_json 'sinnix.runtime.surfaces')"
jq -e '
  (has("agent-gateway-tunnel") | not) and
  ."agent-gateway-observer".unit == "sinnix-agent-gateway-observer.service" and
  ."agent-gateway-observer".activation.publicEndpoint == "127.0.0.1:3088" and
  (has("agent-gateway-operator") | not)
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
test "$(jq -r '.observer.approvedActionCatalogHash' <<<"$endpoints_json")" = "$(jq -r '.sha256' "$catalog_observer")"

jq -e '
  ([.tools[].name] | sort) == ["catalog", "change", "context", "events", "get", "operate", "query", "run", "status", "wait"]
' "$gateway_observer" >/dev/null
jq -e '
  ([.tools[].name] | sort) == ["catalog", "change", "context", "events", "get", "operate", "query", "run", "status", "wait"]
' "$gateway_operator" >/dev/null

printf '%s\n' 'agent-gateway endpoint evaluation and principal manifest checks passed'
