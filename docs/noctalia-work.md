# Native Work rows

The Sinnix hub panel shows the owner queue and exact job/attempt references,
plus up to 40 terminal and hosted conversation destinations from `GET /v1/work`.
Open the panel or select Refresh destinations to read them. Terminal rows come
from Kitty remote control, including ordinary commands without wrappers.
Conversation rows are places; their remote execution state is unknown.

Pins last for the panel process. Refresh retains a saved pin when an owner
restarts or a page navigates. Rebind to current explicitly accepts that row's
new identity. Missing destinations remain stale/unverified. No title or working
directory matching retargets a pin. `POST /v1/work/focus` requires the existing
local capability token and revalidates the full pin before focusing. It never
launches a replacement. A process can still exit between validation and focus.
Queue jobs continue independently of panel and hub lifetimes.

The terminal identity includes boot ID, PID/start ticks, socket inode/path and
Kitty window ID. Conversation identity includes the loopback CDP browser
WebSocket incarnation, page ID and exact URL. Missing readers produce gaps.
The endpoint uses the host's declared PATH for Kitty and loopback CDP on 9222.
The panel adds no glyphs and does not change keyboard bindings.

After integration, open the main-checkout plugin in Noctalia at the actual
screen scale. Run an ordinary terminal command and a queued operation; confirm
named rows and job/attempt references. With two terminals and conversations,
select Focus exact pin and verify the intended Kitty pane/browser page receives
focus. Restart a terminal owner, navigate a conversation, and refresh: old pins
must report stale/unverified; focus must refuse them until an explicit rebind.
Check missing CDP/Kitty observations remain gaps. Confirm F6, F7, F8 and thought
capture retain their behavior. Record the selected plugin path/hash and loaded
bytes when observable. This worktree cannot hot-reload the main-checkout plugin.
