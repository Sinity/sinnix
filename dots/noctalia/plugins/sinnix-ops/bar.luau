--!nonstrict
-- Compact read-only capsule. It only consumes shared bridge state; a click
-- opens the panel.

local view = noctalia.state.get("sinity-ops.view") or { status = "disconnected" }

-- The attention count lives on the dedicated attention widget; this capsule
-- is the connection-status surface only.
local function label()
  local base = "OPS x"
  if view.status == "connected" then base = "OPS" end
  if view.status == "snapshot" then base = "OPS ~" end
  if view.status == "source-stale" or view.status == "stale" then base = "OPS !" end
  if view.status == "aggregate" then base = "OPS ?" end
  return base
end

local function render()
  local color = view.status == "connected" and "primary" or (view.status == "stale" and "error" or "secondary")
  barWidget.render(ui.row({ gap = 5, align = "center" }, {
    ui.glyph({ name = "heartbeat", size = 14, color = color }),
    ui.label({ text = label(), color = color, fontWeight = "bold" }),
  }))
end

noctalia.state.watch("sinity-ops.view", function(value)
  view = type(value) == "table" and value or { status = "disconnected" }
  render()
end)

function onClick()
  noctalia.togglePanel("sinity/sinnix-ops:now")
end

function update()
  render()
end
