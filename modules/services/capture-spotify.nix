# capture-spotify: poll the Spotify Web API's recently-played history into
# the capture lake (sinnix-0s27).
#
# Lives under activityRoot/spotify (not the bead's literal capturesRoot path):
# it predates the 2026-08-17 subject recut that moved every media-playback
# lane there (see capture-mpris.nix, which made the same move for the local
# MPRIS lane) -- the recut's own doctrine wins over a stale literal in an
# older bead.
#
# Credential chain (three secrets, two already in place):
#   spotify-client-id / spotify-client-secret  -- agenix ciphertext already
#     exists (this app was registered on Spotify's developer dashboard
#     out-of-band); auto-discovered by modules/secrets.nix like any other
#     secret/*.age file.
#   spotify-refresh-token -- does NOT exist yet. Spotify's Authorization Code
#     grant needs one user-authorized browser confirmation to mint it; that
#     cannot be scripted headlessly, so it is a *runtime secret contract*
#     (modules/secrets.nix's runtimeSecretContracts) instead of ciphertext:
#     config.sinnix.secrets.paths.spotify-refresh-token resolves and evals
#     cleanly (/run/agenix/spotify-refresh-token) whether or not the file
#     exists. The unit stays enabled below; until the secret lands it fails
#     its own poll with a one-line instruction rather than failing eval.
#
# Operator bootstrap (one command, one browser click):
#   1. sinnix spotify-auth
#      -- prints an authorize URL, opens a local loopback listener, waits.
#   2. Open the printed URL in an authenticated browser and click Allow.
#   3. The script exchanges the code for a refresh token and prints the
#      exact follow-up command:
#        echo -n '<refresh_token>' | agenix -e secret/spotify-refresh-token.age
#      (run from `nix develop`, which is where the `agenix` wrapper lives).
#   4. switch. The next timer tick picks the secret up with no further
#      config change -- the service is already enabled on sinnix-prime.
#
# One-time prerequisite outside any script: the Spotify app's dashboard
# (developer.spotify.com) must list this host's loopback redirect URI
# (http://127.0.0.1:8973/callback, see scripts/sinnix-spotify-auth) under
# "Redirect URIs" -- Spotify validates it against the app's own allowlist and
# there's no API to add it, so `sinnix spotify-auth` cannot do this step for
# the operator; it only needs doing once per app registration.
{
  mkServiceModule,
  mkCaptureLane,
  pkgs,
  lib,
  config,
  helpers,
  ...
}@args:
let
  username = config.sinnix.user.name;
  activityRoot = config.sinnix.paths.activityRoot;
  laneDir = "${activityRoot}/spotify";
  # Mutable runtime state (poll cursor + any rotated refresh token), distinct
  # from the lane directory the same way xiaomi-witness separates its token
  # state from its capture lane -- 0700 because a rotated refresh token can
  # land here, and that's live account credential material.
  stateDir = "/realm/state/capture-spotify";
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  secretPaths = config.sinnix.secrets.paths;
  cfg = config.sinnix.services.capture-spotify;

  poller = pkgs.writeShellApplication {
    name = "capture-spotify-poll";
    runtimeInputs = [
      pkgs.curl
      pkgs.jq
      pkgs.coreutils
    ];
    text = ''
      set -euo pipefail

      client_id_file="$1"
      client_secret_file="$2"
      refresh_token_file="$3"
      state_dir="$4"
      capture_bin="$5"
      capture_root="$6"

      cursor_file="$state_dir/cursor"
      local_refresh_file="$state_dir/refresh-token"

      # A refresh token minted by `sinnix spotify-auth` may get rewritten here
      # if Spotify ever rotates it on a refresh call; prefer that live copy
      # over the agenix-managed original when both exist.
      if [ -s "$local_refresh_file" ]; then
        refresh_token_source="$local_refresh_file"
      elif [ -s "$refresh_token_file" ]; then
        refresh_token_source="$refresh_token_file"
      else
        echo "capture-spotify: no refresh token yet -- run 'sinnix spotify-auth' once (prints an authorize URL + a browser step), then 'echo -n TOKEN | agenix -e secret/spotify-refresh-token.age'" >&2
        exit 1
      fi

      client_id="$(<"$client_id_file")"
      client_secret="$(<"$client_secret_file")"
      refresh_token="$(<"$refresh_token_source")"

      token_response="$(curl -sS --max-time 15 -u "$client_id:$client_secret" \
        -d grant_type=refresh_token --data-urlencode "refresh_token=$refresh_token" \
        https://accounts.spotify.com/api/token)"

      if echo "$token_response" | jq -e 'has("error")' >/dev/null; then
        reason="$(echo "$token_response" | jq -r '.error_description // .error')"
        echo "capture-spotify: token refresh failed ($reason) -- refresh token is likely revoked or stale; re-run 'sinnix spotify-auth'" >&2
        exit 1
      fi
      access_token="$(echo "$token_response" | jq -r '.access_token')"

      # Spotify's confidential-client Authorization Code grant does not
      # rotate refresh tokens today, but persisting a fresh one whenever the
      # response actually carries one costs nothing and survives a future
      # policy change.
      new_refresh="$(echo "$token_response" | jq -r '.refresh_token // empty')"
      if [ -n "$new_refresh" ]; then
        printf '%s' "$new_refresh" > "$local_refresh_file.tmp"
        mv "$local_refresh_file.tmp" "$local_refresh_file"
      fi

      last_cursor_ms=0
      if [ -s "$cursor_file" ]; then
        last_cursor_ms="$(<"$cursor_file")"
      fi

      url="https://api.spotify.com/v1/me/player/recently-played?limit=50"
      if [ "$last_cursor_ms" != "0" ]; then
        url="''${url}&after=''${last_cursor_ms}"
      fi

      # -f here (unlike the token call above): a bad access token or an
      # outage is an ordinary failure worth surfacing as a failed unit, not
      # a case needing a bespoke message.
      response="$(curl -fsS --max-time 15 -H "Authorization: Bearer $access_token" "$url")"

      # played_at carries millisecond fractional seconds ("...123Z"), which
      # jq's fromdateiso8601 (RFC3339, whole seconds only) rejects -- strip
      # the fraction before parsing, keep the millisecond precision only in
      # the cursor arithmetic (* 1000).
      new_items="$(echo "$response" | jq -c --argjson after_ms "$last_cursor_ms" '
        [ .items[]
          | . + { _played_at_ms: ((.played_at | sub("\\.[0-9]+Z$"; "Z") | fromdateiso8601) * 1000) }
        ]
        | map(select(._played_at_ms > $after_ms))
        | sort_by(._played_at_ms)
      ')"

      count="$(echo "$new_items" | jq 'length')"
      if [ "$count" -gt 0 ]; then
        echo "$new_items" | jq -c '.[] | del(._played_at_ms)' \
          | "$capture_bin" write --capture-root "$capture_root" --lane spotify --stream
        max_ms="$(echo "$new_items" | jq '[.[]._played_at_ms] | max')"
        if [ "$max_ms" -gt "$last_cursor_ms" ]; then
          printf '%s' "$max_ms" > "$cursor_file.tmp"
          mv "$cursor_file.tmp" "$cursor_file"
        fi
      fi
    '';
  };
in
mkServiceModule (mkCaptureLane {
  name = "capture-spotify";
  description = "Spotify recently-played listening history capture";
  inherit username laneDir;
  mode = "poll";
  captureName = "spotify";
  # Listening is intermittent by nature -- a quiet day is a legitimate "not
  # listening" outcome, not a broken lane (same reasoning as capture-mpris's
  # week-long budget). The poll cadence itself (well inside the 50-item
  # recently-played wraparound at normal listening pace) is what keeps
  # dedup correct; it says nothing about how long silence is expected.
  eventDriven = true;
  staleAfterSeconds = 604800;
  execStart = lib.concatStringsSep " " [
    "${poller}/bin/capture-spotify-poll"
    secretPaths.spotify-client-id
    secretPaths.spotify-client-secret
    secretPaths.spotify-refresh-token
    stateDir
    "${scriptPkgs.sinnix-capture}/bin/sinnix-capture"
    activityRoot
  ];
  environment = [ "TMPDIR=/tmp" ];
  privateTmp = true;
  tmpfilesRules = [
    "d ${laneDir} 0755 ${username} users -"
    "d ${stateDir} 0700 ${username} users -"
  ];
  writablePaths = [
    laneDir
    stateDir
  ];
  timer = {
    intervalSec = cfg.intervalSec;
    onBootSec = "2min";
    accuracySec = "30s";
  };
  unitDescription = "Poll Spotify recently-played into the capture lake";
  timerDescription = "Periodic trigger for the Spotify listening-history capture";
  extraOptions = {
    intervalSec = lib.mkOption {
      type = lib.types.ints.positive;
      default = 300;
      description = ''
        Seconds between polls. recently-played returns at most the last 50
        plays; even a marathon of one-minute tracks takes ~50 minutes to
        wrap that window, so 5 minutes leaves a wide safety margin against
        ever missing a play between polls.
      '';
    };
  };
}) args
