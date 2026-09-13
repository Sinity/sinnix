--!nonstrict
-- A single stable entry point; no ticking seconds or productivity score.
local activity = noctalia.state.get("sinnix-cockpit.activity")

local function render()
  local value = type(activity) == "table" and activity or {}
  local marker = "open-ended"
  if type(value.reconsider_local) == "string" then marker = string.match(value.reconsider_local, "%s(%d%d:%d%d)") or value.reconsider_local end
  if value.mode == "due" then marker = "next choice" end
  if value.mode == "paused" then marker = "paused" end
  if value.mode == "acknowledged" then marker = "reviewed" end
  if value.mode == "unallocated" then marker = "choose" end
  if value.error ~= nil then marker = "unavailable" end
  barWidget.setTooltip(value.error or ((value.activity or "No activity chosen") .. "\nReconsider: " .. (value.reconsider_local or "open-ended") .. "\nClick / Super+F12: Now\nRight-click / Super+Shift+F12: Capture"))
  barWidget.render(ui.row({ gap = 7, align = "center", paddingH = 8, fill = "#173145", radius = 8 }, {
    ui.label({ text = "Now", fontWeight = "bold", color = "#7bd5ff" }),
    ui.label({ text = value.activity or "Choose activity", maxWidth = 230, maxLines = 1, color = "#f3f7fc" }),
    ui.label({ text = "· " .. marker, color = value.error ~= nil and "error" or "#c3d5e3" }),
  }))
end

noctalia.state.watch("sinnix-cockpit.activity", function(value) activity = value; render() end)
function onClick() noctalia.togglePanel("sinity/sinnix-cockpit:activity-panel") end
function onRightClick() noctalia.togglePanel("sinity/sinnix-cockpit:capture-panel") end
function update() render() end
