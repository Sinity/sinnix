--!nonstrict
-- Cockpit probe. Owns the polling so the widgets stay render-only: every few
-- seconds it asks Hyprland which special workspaces hold windows. No daemon,
-- no timer unit — this runs inside the shell the widgets already live in.

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

noctalia.setUpdateInterval(5000)
pollScratchpads()

function update()
  pollScratchpads()
end
