--!nonstrict
-- Compact read-only capsule. It only consumes shared bridge state.

local view = noctalia.state.get("sinity-ops.view") or { status = "disconnected" }

local function label()
  local attention = view.snapshot and view.snapshot.state and view.snapshot.state.attention
  local count = type(attention) == "table" and tonumber(attention.pending_count) or 0
  local suffix = count > 0 and (" " .. tostring(count)) or ""
  local base = "OPS x"
  if view.status == "connected" then base = "OPS" end
  if view.status == "snapshot" then base = "OPS ~" end
  if view.status == "source-stale" or view.status == "stale" then base = "OPS !" end
  if view.status == "aggregate" then base = "OPS ?" end
  return base .. suffix
end

local function render()
  local color = view.status == "connected" and "primary" or (view.status == "stale" and "error" or "secondary")
  barWidget.render(ui.row({ gap = 5, align = "center" }, {
    ui.glyph({ name = "monitor_heart", size = 14, color = color }),
    ui.label({ text = label(), color = color, fontWeight = "bold" }),
  }))
end

noctalia.state.watch("sinity-ops.view", function(value)
  view = type(value) == "table" and value or { status = "disconnected" }
  render()
end)

function update()
  render()
end
