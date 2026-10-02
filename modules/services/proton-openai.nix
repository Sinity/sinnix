# Proton VPN lane for OpenAI surfaces.
#
# A Proton-generated WireGuard config stays outside the Nix store (normally
# agenix). The tunnel never installs a host-wide default route. A loopback-only
# proxy binds outbound sockets to the tunnel address; source-policy routing then
# sends only those sockets through Proton.
{
  mkServiceModule,
  lib,
  pkgs,
  ...
}@args:
let
  interfaceName = "proton-openai";
  routingTable = 201;
in
mkServiceModule {
  name = "proton-openai";
  description = "Proton WireGuard lane for ChatGPT, Codex and OpenAI web traffic";
  docs = "docs/proton-openai.md";
  extraOptions = {
    wireGuardConfigFile = lib.mkOption {
      type = lib.types.str;
      default = "/run/agenix/proton-openai-wireguard";
      description = "Runtime path to a Proton-generated WireGuard .conf file.";
    };
    proxyPort = lib.mkOption {
      type = lib.types.port;
      default = 8119;
      description = "Loopback HTTP CONNECT proxy port for OpenAI clients.";
    };
  };
  surface = {
    unit = "proton-openai-proxy.service";
    resourceClass = "ordinary";
    observe = {
      enable = true;
      restartable = true;
    };
  };
  configFn =
    { cfg, pkgs, ... }:
    let
      runtimeDir = "/run/sinnix/proton-openai";
      proxyUrl = "http://127.0.0.1:${toString cfg.proxyPort}";

      tunnelUp = pkgs.writeShellApplication {
        name = "proton-openai-up";
        runtimeInputs = [
          pkgs.coreutils
          pkgs.gawk
          pkgs.gnugrep
          pkgs.gnused
          pkgs.iproute2
          pkgs.wireguard-tools
        ];
        text = ''
          set -euo pipefail

          conf=${lib.escapeShellArg cfg.wireGuardConfigFile}
          ifname=${lib.escapeShellArg interfaceName}
          table=${toString routingTable}

          if [ ! -r "$conf" ]; then
            echo "proton-openai: WireGuard config is not readable: $conf" >&2
            exit 1
          fi

          install -d -m 0755 ${runtimeDir}

          if ip link show "$ifname" >/dev/null 2>&1; then
            ip link delete "$ifname"
          fi

          stripped="$(mktemp)"
          trap 'rm -f "$stripped"' EXIT
          install -m 0600 "$conf" ${runtimeDir}/profile.conf
          wg-quick strip ${runtimeDir}/profile.conf >"$stripped"
          rm -f ${runtimeDir}/profile.conf

          ip link add "$ifname" type wireguard
          cleanup() {
            ip link delete "$ifname" 2>/dev/null || true
          }
          trap 'rm -f "$stripped"; cleanup' ERR

          wg setconf "$ifname" "$stripped"

          addresses="$(
            awk -F= '
              /^[[:space:]]*Address[[:space:]]*=/ {
                gsub(/[[:space:]]/, "", $2)
                print $2
              }
            ' "$conf" | tr "," "\n" | sed '/^$/d'
          )"

          if [ -z "$addresses" ]; then
            echo "proton-openai: config has no Interface Address" >&2
            exit 1
          fi

          while IFS= read -r address; do
            case "$address" in
              *:*) ip -6 address add "$address" dev "$ifname" ;;
              *)   ip -4 address add "$address" dev "$ifname" ;;
            esac
          done <<<"$addresses"

          mtu="$(
            awk -F= '
              /^[[:space:]]*MTU[[:space:]]*=/ {
                gsub(/[[:space:]]/, "", $2)
                print $2
                exit
              }
            ' "$conf"
          )"
          if [ -n "$mtu" ]; then
            ip link set mtu "$mtu" dev "$ifname"
          fi
          ip link set "$ifname" up

          ip -4 route replace unreachable default metric 32767 table "$table"
          ip -4 route replace default dev "$ifname" metric 10 table "$table"
          ip -6 route replace default dev "$ifname" table "$table" 2>/dev/null || true

          while IFS= read -r address; do
            source="''${address%/*}"
            case "$address" in
              *:*) ip -6 rule add from "$source" table "$table" priority 120 2>/dev/null || true ;;
              *)   ip -4 rule add from "$source" table "$table" priority 120 2>/dev/null || true ;;
            esac
          done <<<"$addresses"

          bind_ip="$(
            printf '%s\n' "$addresses" |
              awk '!/:/ { sub(/\/.*/, "", $0); print; exit }'
          )"
          if [ -z "$bind_ip" ]; then
            echo "proton-openai: config has no IPv4 tunnel address" >&2
            exit 1
          fi

          printf '%s\n' "$bind_ip" >${runtimeDir}/bind-ip
          printf '%s\n' ${lib.escapeShellArg proxyUrl} >${runtimeDir}/proxy-url

          trap - ERR
          rm -f "$stripped"
        '';
      };

      tunnelDown = pkgs.writeShellApplication {
        name = "proton-openai-down";
        runtimeInputs = [
          pkgs.coreutils
          pkgs.gawk
          pkgs.gnugrep
          pkgs.iproute2
        ];
        text = ''
          set -u
          ifname=${lib.escapeShellArg interfaceName}
          table=${toString routingTable}

          while ip -4 rule show | grep -q "lookup $table"; do
            priority="$(ip -4 rule show | awk -v t="$table" '$0 ~ "lookup " t { sub(/:.*/, "", $1); print $1; exit }')"
            [ -n "$priority" ] || break
            ip -4 rule del priority "$priority" 2>/dev/null || break
          done

          while ip -6 rule show | grep -q "lookup $table"; do
            priority="$(ip -6 rule show | awk -v t="$table" '$0 ~ "lookup " t { sub(/:.*/, "", $1); print $1; exit }')"
            [ -n "$priority" ] || break
            ip -6 rule del priority "$priority" 2>/dev/null || break
          done

          ip -4 route flush table "$table" 2>/dev/null || true
          ip -6 route flush table "$table" 2>/dev/null || true
          ip link delete "$ifname" 2>/dev/null || true
          rm -f ${runtimeDir}/bind-ip ${runtimeDir}/proxy-url ${runtimeDir}/profile.conf
        '';
      };

      proxyStart = pkgs.writeShellApplication {
        name = "proton-openai-proxy-start";
        runtimeInputs = [
          pkgs.coreutils
          pkgs.tinyproxy
        ];
        text = ''
          set -euo pipefail

          bind_file=${runtimeDir}/bind-ip
          if [ ! -s "$bind_file" ]; then
            echo "proton-openai: tunnel did not publish a bind address" >&2
            exit 1
          fi
          bind_ip="$(cat "$bind_file")"

          cat >/run/proton-openai-proxy/tinyproxy.conf <<EOF
          Port ${toString cfg.proxyPort}
          Listen 127.0.0.1
          Bind $bind_ip
          Timeout 600
          MaxClients 100
          Allow 127.0.0.1
          DisableViaHeader Yes
          ConnectPort 80
          ConnectPort 443
          LogLevel Info
          EOF

          exec tinyproxy -d -c /run/proton-openai-proxy/tinyproxy.conf
        '';
      };

      pac = pkgs.writeText "openai-proxy.pac" ''
        function openaiHost(host) {
          return host === "chatgpt.com"
              || dnsDomainIs(host, ".chatgpt.com")
              || host === "openai.com"
              || dnsDomainIs(host, ".openai.com")
              || host === "oaistatic.com"
              || dnsDomainIs(host, ".oaistatic.com")
              || host === "oaiusercontent.com"
              || dnsDomainIs(host, ".oaiusercontent.com");
        }

        function FindProxyForURL(url, host) {
          if (openaiHost(host)) {
            return "PROXY 127.0.0.1:${toString cfg.proxyPort}";
          }
          return "DIRECT";
        }
      '';
    in
    {
      environment.etc."sinnix/openai-proxy.pac".source = pac;
      environment.etc."sinnix/openai-proxy-url".text = "${proxyUrl}\n";

      systemd.services.proton-openai-wg = {
        description = "Proton WireGuard tunnel for OpenAI egress";
        wantedBy = [ "multi-user.target" ];
        before = [ "proton-openai-proxy.service" ];
        after = [ "network-online.target" ];
        wants = [ "network-online.target" ];
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
          ExecStart = "${tunnelUp}/bin/proton-openai-up";
          ExecStopPost = "${tunnelDown}/bin/proton-openai-down";
          TimeoutStartSec = "30s";
          TimeoutStopSec = "10s";
        };
      };

      systemd.services.proton-openai-proxy = {
        description = "Loopback OpenAI proxy bound to Proton VPN";
        wantedBy = [ "multi-user.target" ];
        after = [
          "network-online.target"
          "proton-openai-wg.service"
        ];
        wants = [ "network-online.target" ];
        requires = [ "proton-openai-wg.service" ];
        unitConfig.PartOf = [ "proton-openai-wg.service" ];
        serviceConfig = {
          Type = "simple";
          DynamicUser = true;
          RuntimeDirectory = "proton-openai-proxy";
          NoNewPrivileges = true;
          ProtectSystem = "strict";
          ProtectHome = true;
          ExecStart = "${proxyStart}/bin/proton-openai-proxy-start";
          Restart = "on-failure";
          RestartSec = "3s";
        };
      };
    };
} args
