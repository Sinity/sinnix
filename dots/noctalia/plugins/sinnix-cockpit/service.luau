--!nonstrict
-- Cockpit probe. Owns the polling so the widgets stay render-only: every few
-- seconds it asks Hyprland which special workspaces hold windows, and it
-- rereads the capability index when the file's mtime moves. No daemon, no
-- timer unit — this runs inside the shell the widgets already live in.

local INDEX_PATH = noctalia.getConfig("index_path") or "/etc/sinnix/capability-index.json"

-- Scratchpad name -> the special workspace its verb toggles. These mirror the
-- F8/F6/F7 binds (toggle-scratch specs in hyprland/scratchpads.nix and the
-- direct togglespecialworkspace dispatch for the agent browser).
local TARGETS = {
  rawlog = "special:scratch_rawlog",
  weechat = "special:scratch_weechat",
  agentbrowser = "special:agentbrowser",
}

local polling = false

local function pollScratchpads()
  if polling then return end
  polling = true
  local accepted = noctalia.runAsync("hyprctl -j clients", function(result)
    polling = false
    if result.exitCode ~= 0 or result.timedOut then
      noctalia.state.set("sinnix-cockpit.scratch", nil)
      return
    end
    local clients = noctalia.json.decode(result.stdout)
    if type(clients) ~= "table" then return end
    local presence = {}
    for name in pairs(TARGETS) do
      presence[name] = false
    end
    for _, client in ipairs(clients) do
      local workspace = type(client) == "table" and type(client.workspace) == "table" and client.workspace.name or nil
      for name, target in pairs(TARGETS) do
        if workspace == target then presence[name] = true end
      end
    end
    noctalia.state.set("sinnix-cockpit.scratch", presence)
  end, 5000)
  if not accepted then polling = false end
end

local indexMtime = nil

local function readIndex()
  local info = noctalia.fileInfo(INDEX_PATH)
  local mtime = type(info) == "table" and info.mtime or nil
  if mtime ~= nil and mtime == indexMtime then return end
  indexMtime = mtime
  local raw = noctalia.readFile(INDEX_PATH)
  if raw == nil then
    noctalia.state.set("sinnix-cockpit.capabilities", nil)
    return
  end
  local index = noctalia.json.decode(raw)
  if type(index) ~= "table" or index.schema ~= "sinnix-capability-index-v1" or type(index.rows) ~= "table" then
    noctalia.state.set("sinnix-cockpit.capabilities", { schema_mismatch = true })
    return
  end
  local kinds = {}
  for _, row in ipairs(index.rows) do
    local kind = type(row) == "table" and row.kind or nil
    if type(kind) == "string" then kinds[kind] = (kinds[kind] or 0) + 1 end
  end
  noctalia.state.set("sinnix-cockpit.capabilities", {
    total = #index.rows,
    kinds = kinds,
    revision = index.revision,
  })
end

noctalia.setUpdateInterval(5000)
pollScratchpads()
readIndex()

function update()
  pollScratchpads()
  readIndex()
end
