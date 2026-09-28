#!/usr/bin/env bash
# Claude Code statusLine — mirrors Starship prompt style (Gruvbox base16)
# Left:  <cwd> [branch][git-status] [nix] | <model>
# Right: <context%> <time>

input=$(cat)

# --- Fields from JSON ---
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // empty')
model=$(echo "$input" | jq -r '.model.display_name // empty')
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
remaining_pct=$(echo "$input" | jq -r '.context_window.remaining_percentage // empty')
# Subscription usage: "<5h%> <5h reset epoch> <7d%> <7d reset epoch>", empty
# when Claude Code has no reading.
read -r q5 q5_reset q7 q7_reset < <(echo "$input" | jq -r '
  .rate_limits // empty
  | select(.five_hour != null)
  | "\(.five_hour.used_percentage) \(.five_hour.resets_at) \(.seven_day.used_percentage // "null") \(.seven_day.resets_at // "null")"')

# Append each changed reading to claude-quota's history, which computes the
# burn rate from it.
if [ -n "${q5:-}" ]; then
  quota_state="${XDG_STATE_HOME:-$HOME/.local/state}/claude-quota"
  quota_key="$q5 $q5_reset $q7"
  if [ "$(cat "$quota_state/last-statusline" 2>/dev/null)" != "$quota_key" ]; then
    mkdir -p "$quota_state"
    printf '%s' "$quota_key" >"$quota_state/last-statusline"
    printf '{"ts":%s,"source":"statusline","five_hour":%s,"five_hour_resets_at":%s,"seven_day":%s,"seven_day_resets_at":%s}\n' \
      "$(date +%s)" "$q5" "$q5_reset" "$q7" "$q7_reset" >>"$quota_state/samples.jsonl"
  fi
fi

# Git branch/status (from workspace repo + worktree fields)
git_branch=$(echo "$input" | jq -r '.worktree.branch // empty')
if [ -z "$git_branch" ]; then
  git_branch=$(GIT_OPTIONAL_LOCKS=0 git -C "$cwd" symbolic-ref --short HEAD 2>/dev/null || true)
fi

git_status_flags=""
if [ -n "$git_branch" ]; then
  git_flags=$(GIT_OPTIONAL_LOCKS=0 git -C "$cwd" status --porcelain 2>/dev/null | head -20)
  if [ -n "$git_flags" ]; then
    has_staged=$(echo "$git_flags" | grep -c '^[MADRC]' || true)
    has_modified=$(echo "$git_flags" | grep -c '^.[MD]' || true)
    has_untracked=$(echo "$git_flags" | grep -c '^??' || true)
    [ "$has_staged" -gt 0 ] && git_status_flags="${git_status_flags}+"
    [ "$has_modified" -gt 0 ] && git_status_flags="${git_status_flags}*"
    [ "$has_untracked" -gt 0 ] && git_status_flags="${git_status_flags}?"
  fi
fi

# Shorten cwd: replace $HOME with ~, fish-style abbrev for long paths
if [ -n "$cwd" ]; then
  home_dir="$HOME"
  display_cwd="${cwd/#$home_dir/\~}"
  # Fish-style: shorten each non-final component to first char
  IFS='/' read -ra parts <<<"$display_cwd"
  last_idx=$((${#parts[@]} - 1))
  short_path=""
  for i in "${!parts[@]}"; do
    part="${parts[$i]}"
    if [ "$i" -eq "$last_idx" ]; then
      short_path="${short_path}${part}"
    elif [ -z "$part" ]; then
      short_path="/"
    elif [ "${part:0:1}" = "~" ]; then
      short_path="${part}/"
    else
      short_path="${short_path}${part:0:1}/"
    fi
  done
  display_cwd="$short_path"
fi

# ANSI colors (Gruvbox palette, dimmed for status line context)
# cyan bold -> directory
# yellow -> branch
# red -> git status flags
# blue bold -> nix indicator (if in nix shell)
# white/default -> separator
CYAN='\033[36m'
YELLOW='\033[33m'
RED='\033[31m'
BLUE='\033[34m'
DIM='\033[2m'
RESET='\033[0m'

# --- Assemble left side ---
left=""

# Directory (cyan)
if [ -n "$display_cwd" ]; then
  left="${left}$(printf "${CYAN}%s${RESET}" "$display_cwd")"
fi

# Branch (yellow) + status (red)
if [ -n "$git_branch" ]; then
  left="${left} $(printf "${YELLOW}%s${RESET}" "$git_branch")"
  if [ -n "$git_status_flags" ]; then
    left="${left}$(printf "${RED}%s${RESET}" "$git_status_flags")"
  fi
fi

# Nix shell indicator
if [ -n "${IN_NIX_SHELL:-}" ] || [ -n "${NIX_BUILD_TOP:-}" ]; then
  left="${left} $(printf "${BLUE}N${RESET}")"
fi

# Model
if [ -n "$model" ]; then
  left="${left} ${DIM}|${RESET} ${DIM}${model}${RESET}"
fi

# --- Assemble right side ---
right=""

# Context usage
if [ -n "$used_pct" ] && [ -n "$remaining_pct" ]; then
  pct_int=$(printf '%.0f' "$used_pct")
  if [ "$pct_int" -ge 80 ]; then
    color="$RED"
  elif [ "$pct_int" -ge 50 ]; then
    color="$YELLOW"
  else
    color="$DIM"
  fi
  right="${right}$(printf "${color}ctx:%s%%${RESET}" "$pct_int")"
fi

# 5-hour subscription usage and its reset time
if [ -n "${q5:-}" ]; then
  q5_int=$(printf '%.0f' "$q5")
  if [ "$q5_int" -ge 90 ]; then
    color="$RED"
  elif [ "$q5_int" -ge 70 ]; then
    color="$YELLOW"
  else
    color="$DIM"
  fi
  right="${right} $(printf "${color}5h:%s%%→%s${RESET}" "$q5_int" "$(date -d "@${q5_reset%.*}" +%H:%M)")"
fi

# Time (dimmed, HH:MM)
right="${right} $(printf "${DIM}%s${RESET}" "$(date +%H:%M)")"

# --- Print with left/right layout ---
if [ -n "$right" ]; then
  printf "%b  %b" "$left" "$right"
else
  printf "%b" "$left"
fi
