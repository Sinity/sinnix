#!/usr/bin/env bash
# SessionStart hook — tell the agent which services are down ON PURPOSE.
#
# Without this, every fresh session that looks at the machine rediscovers an
# intentional outage as an emergency and reports it as a finding. The
# acknowledgements live in the runtime inventory next to the surfaces they
# describe (sinnix.runtime.surfaces.<name>.acknowledged); `sinnix orient
# --acknowledged-only` reads that same declared state directly (a fast static
# read, socket fallback only if the file is unreadable), so this hook is not
# a second implementation of the read, just its session-start front door.
#
# Silent when there is nothing acknowledged, and silent on any error: a
# session must never fail to start because a status preamble could not render.

command -v sinnix-orient >/dev/null 2>&1 || exit 0
exec sinnix-orient --acknowledged-only
