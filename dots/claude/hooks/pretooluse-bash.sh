#!/usr/bin/env bash
# PreToolUse hook for Bash commands.
#
# Blocks dangerous patterns only. Build/test/resource placement is provided by
# project dev environments, not by this hook.

set -euo pipefail

INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
HOOK_CWD=$(echo "$INPUT" | jq -r '.cwd // .tool_input.cwd // ""')

egress_decision="$(SINNIX_HOOK_COMMAND="$CMD" SINNIX_HOOK_CWD="$HOOK_CWD" sinnix-egress-scan 2>/dev/null || true)"
if [[ -n $egress_decision ]] && jq -e '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null <<<"$egress_decision"; then
  printf '%s\n' "$egress_decision"
  exit 0
fi

bd_guard_reason=""
bd_guard_script=$(
  cat <<'PY'
import json
import os
import shlex
import sys

command = os.environ.get("SINNIX_HOOK_COMMAND", "")
cwd = os.environ.get("SINNIX_HOOK_CWD", "")
try:
    tokens = list(shlex.shlex(command, posix=True, punctuation_chars=";&|"))
except ValueError:
    sys.exit(0)

separators = {";", "&", "|", "&&", "||"}
command_start = True
replace_flags = {"--notes", "--design", "--description", "-d"}


def deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def is_absolute(value):
    return value.startswith("/")


def has_absolute_option(segment, names):
    for position, option in enumerate(segment):
        if option in names and position + 1 < len(segment) and is_absolute(segment[position + 1]):
            return True
        if any(option.startswith(name + "=") and is_absolute(option.split("=", 1)[1]) for name in names):
            return True
    return False

for index, token in enumerate(tokens):
    if token in separators:
        command_start = True
        continue
    if command_start and token == "bd" and index + 1 < len(tokens) and tokens[index + 1] == "update":
        end = index + 2
        while end < len(tokens) and tokens[end] not in separators:
            end += 1
        for option in tokens[index + 2 : end]:
            if option in replace_flags or any(option.startswith(flag + "=") for flag in replace_flags):
                deny("bd update replace-writes blocked: use --append-notes for note history, --design-file or --body-file for file-backed updates, or read-modify-write when replacing a field is intentional.")
        sys.exit(0)
    if cwd == "/realm/worktrees" or cwd.startswith("/realm/worktrees/"):
        end = index + 1
        while end < len(tokens) and tokens[end] not in separators:
            end += 1
        segment = tokens[index:end]
        if token == "git" and "commit" in segment and not has_absolute_option(segment, {"-C"}):
            deny("wrong-checkout guard: git commit from a worktree requires git -C /absolute/repository; verify the checkout before committing.")
        if token == "bd" and "export" in segment:
            explicit_directory = has_absolute_option(segment, {"-C", "--directory"})
            explicit_output = has_absolute_option(segment, {"-o", "--output"})
            if not explicit_directory and not explicit_output:
                deny("wrong-checkout guard: bd export from a worktree requires bd -C /absolute/repository export or -o /absolute/output.")
    command_start = False
PY
)
bd_guard_reason="$(SINNIX_HOOK_COMMAND="$CMD" SINNIX_HOOK_CWD="$HOOK_CWD" python3 -c "$bd_guard_script")"
if [[ -n $bd_guard_reason ]]; then
  printf '%s\n' "$bd_guard_reason"
  exit 0
fi

emit_deny() {
  local reason="$1"
  jq -n --arg reason "$reason" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $reason
    }
  }'
}

# --- Denials -----------------------------------------------------------------

# Block imperative package installs.
# Only at command start or after a command separator — not inside heredocs or strings.
if echo "$CMD" | grep -qE '(^|[;&|]\s*)(nix\s+profile\s+(install|add|remove)|cargo\s+install|pip3?\s+install|npm\s+install\s+-g)'; then
  emit_deny "Use declarative config instead of imperative install"
  exit 0
fi

# Block bare force-push (-f, --force) but allow safer variants
# (--force-with-lease, --force-if-includes).
if echo "$CMD" | grep -qE 'git\s+push\s+.*(-f(\s|$)|--force(\s|$))'; then
  emit_deny "Bare force-push blocked — use --force-with-lease or --force-if-includes"
  exit 0
fi

# Block shell glob expansion over /nix/store.
#
# /nix/store holds ~219k top-level entries on this host, on the SATA SSD. A
# pattern like /nix/store/*/share/doc/pkg/*.html makes the SHELL readdir all
# of them and then opendir one subpath per entry, building the match list in
# RAM before the command it was written for ever runs. Twice now that has
# taken the machine down: most recently 8.3 GB RSS + 11.8 GB swap held by a
# zsh stuck in D state for 22 minutes, exhausting all 19 GB of swap and
# driving memory PSI to 51 while an unrelated agent session did nothing wrong
# but wait. The command in that incident was an `rg`, which is why it reads
# like a ripgrep problem; ripgrep never started.
#
# Matches only an unquoted glob in the segment right after /nix/store/, so a
# concrete store path stays allowed, and so does a quoted pattern handed to a
# tool that expands it lazily itself (find -name, rg --glob).
#
# Heredoc bodies are stripped first: a commit message or doc that describes
# this very hazard must be able to quote the pattern. Found by dogfooding —
# the commit introducing this guard was blocked by it.
CMD_NO_HEREDOC=$(printf '%s' "$CMD" | awk '
  BEGIN { term = "" }
  term != "" { if ($0 == term) { term = "" } ; next }
  {
    line = $0
    if (match(line, /<<-?[[:space:]]*'"'"'?"?[A-Za-z_][A-Za-z0-9_]*'"'"'?"?/)) {
      tag = substr(line, RSTART, RLENGTH)
      gsub(/^<<-?[[:space:]]*/, "", tag)
      gsub(/['"'"'"]/, "", tag)
      term = tag
    }
    print line
  }')
if echo "$CMD_NO_HEREDOC" | grep -qE "(^|[^'\"])/nix/store/[^[:space:]'\"]*[*?]"; then
  emit_deny "Shell glob over /nix/store blocked: ~219k entries make the shell stat the whole store before your command runs (this has OOMed the host twice). Use 'find /nix/store -maxdepth 1 -name PATTERN' which streams, or resolve the one store path first (nix eval --raw, readlink, nix-locate) and search under that."
  exit 0
fi

exit 0
