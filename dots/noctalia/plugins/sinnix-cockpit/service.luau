--!nonstrict
-- Cockpit probe. Owns the polling so the widgets stay render-only: every few
-- seconds it asks Hyprland which scratch or agent workspaces hold windows, and it
-- rereads the capability index when the file's mtime moves. No daemon, no
-- timer unit — this runs inside the shell the widgets already live in.

local INDEX_PATH = noctalia.getConfig("index_path") or "/etc/sinnix/capability-index.json"
-- The reading stack's working state, written atomically by sinnix-reading-stack.
local STACK_PATH = noctalia.expandPath("~/.local/state/sinnix/reading-stack.json")

-- Surface name -> the workspace its verb toggles. These mirror the F8/F6/F7
-- binds: two special scratchpads and the ordinary named agent-browser workspace.
local TARGETS = {
  rawlog = "special:scratch_rawlog",
  weechat = "special:scratch_weechat",
  agentbrowser = "agentbrowser",
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

local stackMtime = nil

local function readStack()
  local info = noctalia.fileInfo(STACK_PATH)
  local mtime = type(info) == "table" and info.mtime or nil
  if mtime ~= nil and mtime == stackMtime then return end
  stackMtime = mtime
  local raw = noctalia.readFile(STACK_PATH)
  if raw == nil then
    -- No file yet means nothing was ever pushed: an empty stack, not an error.
    noctalia.state.set("sinnix-cockpit.reading-stack", { total = 0, items = {} })
    return
  end
  local items = noctalia.json.decode(raw)
  if type(items) ~= "table" then
    noctalia.state.set("sinnix-cockpit.reading-stack", nil)
    return
  end
  local head = {}
  for index, item in ipairs(items) do
    if index > 12 then break end
    if type(item) == "table" then
      table.insert(head, { title = item.title, url = item.url })
    end
  end
  noctalia.state.set("sinnix-cockpit.reading-stack", { total = #items, items = head })
end

noctalia.setUpdateInterval(5000)
pollScratchpads()
readIndex()
readStack()

function update()
  pollScratchpads()
  readIndex()
  readStack()
end
