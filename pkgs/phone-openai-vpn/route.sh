#!/system/bin/sh
# Root-only Android kernel WireGuard lane. Magisk runs `up` once at boot.
set -eu
state=/data/adb/sinnix/proton-openai
rootfs=/data/adb/modules/sinnix_debian_chroot/rootfs
iface=sinnix-openai
table=201
package=com.openai.chatgpt
wg() { chroot "$rootfs" /usr/bin/wg "$@"; }
uid_file="$state/uid"

remove_rules() {
    if [ -r "$uid_file" ]; then
        app_uid=$(cat "$uid_file")
        ip -4 rule del priority 100 uidrange "$app_uid-$app_uid" table "$table" 2>/dev/null || true
        ip -6 rule del priority 100 uidrange "$app_uid-$app_uid" table "$table" 2>/dev/null || true
    fi
    ip -4 rule del priority 101 table "$table" 2>/dev/null || true
    ip -6 rule del priority 101 table "$table" 2>/dev/null || true
}

case "${1:-up}" in
    down)
        remove_rules
        iptables -t nat -D POSTROUTING -o "$iface" -j MASQUERADE 2>/dev/null || true
        ip link del "$iface" 2>/dev/null || true
        ip -4 route flush table "$table" 2>/dev/null || true
        ip -6 route flush table "$table" 2>/dev/null || true
        exit 0
        ;;
    status)
        ip link show "$iface"
        wg show "$iface" latest-handshakes
        wg show "$iface" transfer
        ip -4 route show table "$table"
        exit 0
        ;;
    up) ;;
    *) echo 'usage: route.sh up|down|status' >&2; exit 2 ;;
esac

[ -r "$state/profile.conf" ]
[ -x "$rootfs/usr/bin/wg" ]
attempt=0
while :; do
    app_uid=$(cmd package list packages -U "$package" 2>/dev/null | sed -n "s/^package:$package uid://p")
    [ -n "$app_uid" ] && break
    attempt=$((attempt + 1))
    [ "$attempt" -lt 60 ] || { echo 'ChatGPT package UID unavailable' >&2; exit 1; }
    sleep 2
done
case "$app_uid" in *[!0-9]*|'') echo 'invalid app UID' >&2; exit 1 ;; esac
remove_rules
printf '%s\n' "$app_uid" > "$uid_file"
# Keep a terminal route even if the interface later disappears.
ip -4 route replace unreachable default metric 32767 table "$table"
ip -6 route replace unreachable default metric 32767 table "$table"
ip -4 rule add priority 100 uidrange "$app_uid-$app_uid" table "$table"
ip -6 rule add priority 100 uidrange "$app_uid-$app_uid" table "$table"
ip link del "$iface" 2>/dev/null || true
ip link add "$iface" type wireguard
umask 077
conf="$rootfs/tmp/sinnix-openai.conf"
trap 'rm -f "$conf"' EXIT
# wg accepts the core fields; DNS and routing are owned by this lane.
sed -E '/^[[:space:]]*(Address|DNS|MTU|Table|PreUp|PostUp|PreDown|PostDown|SaveConfig)[[:space:]]*=/d' "$state/profile.conf" > "$conf"
wg setconf "$iface" /tmp/sinnix-openai.conf
# Android's protected-socket bit keeps the tunnel's UDP socket outside Tailscale.
wg set "$iface" fwmark 0x20000
addresses=$(sed -n 's/^[[:space:]]*Address[[:space:]]*=[[:space:]]*//p' "$state/profile.conf" | tr ',' ' ')
bind_ip=
for address in $addresses; do
    case "$address" in
        *:*) : ;;
        *) ip -4 address add "$address" dev "$iface"; bind_ip=${address%/*} ;;
    esac
done
[ -n "$bind_ip" ]
ip link set "$iface" mtu 1280 up
# Android may retain the source chosen by netd before UID policy routing.
# Translate only packets that actually leave through this dedicated interface.
iptables -t nat -C POSTROUTING -o "$iface" -j MASQUERADE 2>/dev/null ||
    iptables -t nat -A POSTROUTING -o "$iface" -j MASQUERADE
ip -4 route replace default dev "$iface" metric 10 table "$table"

# This kernel has no IPv6 NAT. Keep app IPv6 terminal so it uses IPv4.
# Bound-interface diagnostic sockets follow the same lane as the app.
ip -4 rule add priority 101 from "$bind_ip" table "$table"
echo 'ChatGPT UID routed through Proton; other app routing unchanged'
