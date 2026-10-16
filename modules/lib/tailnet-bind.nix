# Resolve a verified local tailnet identity without replacing prior evidence on failure.
{
  pkgs,
  lib,
  interface,
}:
name: key: label:
pkgs.writeShellScript name ''
  set -euo pipefail
  target="$1"
  target_dir="$(${pkgs.coreutils}/bin/dirname "$target")"
  ${pkgs.coreutils}/bin/mkdir -p "$target_dir"
  for _ in $(${pkgs.coreutils}/bin/seq 1 60); do
    address="$(${pkgs.iproute2}/bin/ip -4 -o addr show dev ${interface} 2>/dev/null \
      | ${pkgs.gawk}/bin/awk '{print $4}' \
      | ${pkgs.coreutils}/bin/cut -d/ -f1 \
      | ${pkgs.coreutils}/bin/head -n1)"
    if [ -n "''${address:-}" ]; then
      ${lib.optionalString (key == "SINNIX_HUB_TAILNET_IP") ''
        if ! dns_name="$(${pkgs.coreutils}/bin/timeout 5 ${pkgs.tailscale}/bin/tailscale status --json --peers=false \
          | ${pkgs.jq}/bin/jq -er --arg address "$address" '
            .Self
            | select((.TailscaleIPs | type) == "array" and (.TailscaleIPs | index($address)) != null)
            | .DNSName | select(type == "string") | rtrimstr(".")
            | select(length > 0 and length <= 253)
            | select(test("[^A-Za-z0-9.-]") | not)
            | select(split(".") | all(length > 0 and length <= 63 and test("^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?$")))
          ')"; then
          echo "${label}: cannot verify tailnet DNS identity for the bind address; refusing to start" >&2
          exit 1
        fi
      ''}
      temporary="$(${pkgs.coreutils}/bin/mktemp "$target_dir/.${key}.tmp.XXXXXX")"
      trap 'rm -f "$temporary"' EXIT
      ${pkgs.coreutils}/bin/printf '${key}=%s\n' "$address" > "$temporary"
      ${lib.optionalString (key == "SINNIX_HUB_TAILNET_IP") ''
        ${pkgs.coreutils}/bin/printf 'SINNIX_HUB_DNS_NAME=%s\n' "$dns_name" >> "$temporary"
      ''}
      ${pkgs.coreutils}/bin/sync -f "$temporary"
      ${pkgs.coreutils}/bin/mv -f "$temporary" "$target"
      ${pkgs.coreutils}/bin/sync -f "$target_dir"
      trap - EXIT
      exit 0
    fi
    ${pkgs.coreutils}/bin/sleep 2
  done
  echo "${label}: ${interface} has no IPv4 address; refusing to start" >&2
  exit 1
''
