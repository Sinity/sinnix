set -euo pipefail

# Args (all supplied by capture-router.nix's ExecStart, all Nix store paths
# or config values -- never user input):
#   $1 host              ssh target (the operator's existing sinnix-gw alias)
#   $2 capture_bin       sinnix-capture CLI
#   $3 capture_root      local lane root, .../captures/router
#   $4 remote_poll_script    store path to remote-poll.sh
#   $5 remote_periods_script store path to remote-periods.sh
host="$1"
capture_bin="$2"
capture_root="$3"
remote_poll_script="$4"
remote_periods_script="$5"

state_dir="$capture_root/.state"
mkdir -p "$state_dir"

# POSIX single-quote a value for safe embedding in a remote shell command
# line. ssh flattens all trailing argv into one string that the remote shell
# re-splits on whitespace, so local shell quoting does not survive the hop by
# itself: without this, a syslog first line carrying spaces and single quotes
# word-splits into garbage positional args on the router.
sq() {
	printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"
}

watermark_file="$state_dir/syslog-watermark"
prev_offset="0"
prev_first_line=""
if [ -s "$watermark_file" ]; then
	prev_offset="$(sed -n '1p' "$watermark_file")"
	prev_first_line="$(sed -n '2p' "$watermark_file")"
fi

remote_cmd="sh -s -- $(sq "$prev_offset") $(sq "$prev_first_line")"

# Do NOT inherit the operator's interactive ssh config: it is a Home-Manager
# symlink into the nix store, and under this unit's ProtectHome sandbox ssh
# rejects it outright ("Bad owner or permissions on ~/.ssh/config", exit 255).
# A capture lane should not depend on interactive config anyway -- state the
# identity and host key policy explicitly so the lane behaves identically
# whether a human or a timer runs it.
# An array, not a string: an unquoted string expansion is what shellcheck
# rightly rejects (SC2086), and quoting it would pass every flag as one
# argument.
ssh_opts=(
	-F /dev/null
	-o BatchMode=yes
	-o ConnectTimeout=10
	-o StrictHostKeyChecking=accept-new
	-o "UserKnownHostsFile=${ROUTER_KNOWN_HOSTS:-$HOME/.ssh/known_hosts}"
	-o IdentitiesOnly=yes
	-i "${ROUTER_IDENTITY:-$HOME/.ssh/id_ed25519}"
	-o "User=${ROUTER_USER:-root}"
)

out_file="$(mktemp)"
err_file="$(mktemp)"
trap 'rm -f "$out_file" "$err_file"' EXIT

# shellcheck disable=SC2029  # client-side expansion is intended: the
# remote command is built here and the args are single-quote escaped above.
ssh "${ssh_opts[@]}" "$host" "$remote_cmd" \
	<"$remote_poll_script" >"$out_file" 2>"$err_file"

watermark_line="$(grep '^WATERMARK ' "$err_file" | tail -n1 || true)"
if [ -z "$watermark_line" ]; then
	echo "capture-router-poll: no WATERMARK line in remote output -- poll failed" >&2
	cat "$err_file" >&2
	exit 1
fi
wm="${watermark_line#WATERMARK }"
new_offset="${wm%%|*}"
new_first_line="${wm#*|}"

# Pull out one delimited section of the combined remote poll output.
section() {
	awk -v start="===$1===" -v stop="===$2===" \
		'index($0,start)==1{f=1;next} index($0,stop)==1{f=0} f' "$out_file"
}

leases_json="$(section LEASES ASSOC | jq -R -s '
	split("\n") | map(select(length>0)) | map(split(" ")) |
	map({expires:(.[0]|tonumber), mac:.[1], ip:.[2], hostname:.[3], client_id:(.[4] // null)})
')"
echo "$leases_json" | "$capture_bin" write --capture-root "$capture_root" --lane leases

assoc_json="$(section ASSOC NLBW_PERIODS | jq -R -s '
	split("\n") | map(select(length>0)) | map(split("\t")) |
	map({ap:.[0], data:(.[1] // "{}" | fromjson)})
')"
echo "{\"aps\":$assoc_json}" | "$capture_bin" write --capture-root "$capture_root" --lane associations

# Tab-separated nlbw CSV (header + rows) -> a JSON array of row objects, with
# the numeric columns coerced to numbers.
nlbw_csv_to_json() {
	jq -R -s '
		split("\n") | map(select(length>0)) |
		map(split("\t") | map(gsub("^\"|\"$";""))) |
		(.[0]) as $hdr | .[1:] | map(
			([$hdr, .] | transpose | map({(.[0]): .[1]}) | add) as $row
			| $row
			| .family |= tonumber | .port |= tonumber | .conns |= tonumber
			| .rx_bytes |= tonumber | .rx_pkts |= tonumber
			| .tx_bytes |= tonumber | .tx_pkts |= tonumber
		)
	'
}

current_rows="$(section NLBW_CURRENT SYSLOG | nlbw_csv_to_json)"
printf '{"period":"current","rows":%s}' "$current_rows" |
	"$capture_bin" write --capture-root "$capture_root" --lane nlbw

# nlbwmon archives a closed month once and never changes it again, so each
# period is only ever fetched and captured once (see remote-periods.sh).
periods_remote="$(section NLBW_PERIODS NLBW_CURRENT)"
captured_periods_file="$state_dir/nlbw-captured-periods"
touch "$captured_periods_file"

new_periods=""
while IFS= read -r p; do
	[ -n "$p" ] || continue
	if ! grep -qxF "$p" "$captured_periods_file"; then
		new_periods="$new_periods $p"
	fi
done < <(printf '%s\n' "$periods_remote")

if [ -n "$new_periods" ]; then
	# shellcheck disable=SC2086 # intentional word-splitting of the period list
	set -- $new_periods
	# shellcheck disable=SC2029  # period ids are ours and are expanded here on purpose
	periods_out="$(ssh "${ssh_opts[@]}" "$host" "sh -s -- $*" <"$remote_periods_script")"
	for p in "$@"; do
		rows="$(printf '%s\n' "$periods_out" |
			awk -v start="===NLBW_PERIOD:$p===" 'index($0,start)==1{f=1;next} /^===NLBW_PERIOD:/{f=0} f' |
			nlbw_csv_to_json)"
		printf '{"period":"%s","rows":%s}' "$p" "$rows" |
			"$capture_bin" write --capture-root "$capture_root" --lane nlbw
		echo "$p" >>"$captured_periods_file"
	done
fi

# A quiet router produces no new syslog lines most polls -- that is normal,
# not an outage, so no envelope is written for an empty delta (unlike the
# other three sub-lanes, which always write a record even when empty).
syslog_lines="$(section SYSLOG END)"
if [ -n "$syslog_lines" ]; then
	syslog_json="$(printf '%s' "$syslog_lines" | jq -R -s 'split("\n") | map(select(length>0))')"
	printf '{"lines":%s}' "$syslog_json" |
		"$capture_bin" write --capture-root "$capture_root" --lane syslog
fi

printf '%s\n%s\n' "$new_offset" "$new_first_line" >"$watermark_file"
