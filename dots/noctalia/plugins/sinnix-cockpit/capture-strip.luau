--!nonstrict
-- Capture strip: the earned capture verbs as always-visible buttons. Each
-- click runs exactly what the matching F-key bind runs through uwsm, so the
-- application scope and environment are identical to the keybind,
-- and the button lights up while the scratchpad holds a window, so the strip
-- doubles as presence state for all three live surfaces.

local toggleScratch = noctalia.expandPath("~/.local/bin/toggle-scratch")

local VERBS = {
  {
    name = "rawlog",
    glyph = "note",
    tooltip = "Raw-log scratchpad (F8)",
    command = "uwsm app -- " .. toggleScratch .. " rawlog",
  },
  {
    name = "weechat",
    glyph = "messages",
    tooltip = "WeeChat scratchpad (F6)",
    command = "uwsm app -- " .. toggleScratch .. " weechat",
  },
  {
    name = "agentbrowser",
    glyph = "world-search",
    tooltip = "Agent browser (F7)",
    command = "sinnix-chrome-control toggle-agent-workspace",
  },
}

local presence = noctalia.state.get("sinnix-cockpit.scratch")

local function render()
  local buttons = {}
  for _, verb in ipairs(VERBS) do
    local present = type(presence) == "table" and presence[verb.name] == true
    table.insert(
      buttons,
      ui.button({
        key = verb.name,
        glyph = verb.glyph,
        variant = present and "primary" or "ghost",
        controlSize = "sm",
        tooltip = verb.tooltip,
        onClick = function()
          if not noctalia.runAsync(verb.command) then
            noctalia.notifyError("Could not dispatch " .. verb.name)
          end
        end,
      })
    )
  end
  barWidget.render(ui.row({ gap = 2, align = "center" }, buttons))
end

noctalia.state.watch("sinnix-cockpit.scratch", function(value)
  presence = value
  render()
end)

function update()
  render()
end
