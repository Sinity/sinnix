--!nonstrict
-- The number of things waiting on the operator, from the operator-state
-- engine in the hub server. Zero means nothing needs him. A click opens the
-- panel. The capsule computes nothing: it shows the count it is given.

local view = noctalia.state.get("sinity-hub.view") or { status = "disconnected" }

local function waiting()
  local snapshot = view.snapshot
  local state = type(snapshot) == "table" and type(snapshot.state) == "table" and snapshot.state.operator_state or nil
  local counts = type(state) == "table" and state.counts or nil
  if type(counts) ~= "table" or type(counts.waiting) ~= "number" then return nil end
  return counts.waiting
end

local function render()
  local count = waiting()
  local stale = view.status == "stale" or view.status == "disconnected"
  -- "?" when the count is unknown; a trailing "~" when it may be out of date.
  local label = count == nil and "?" or tostring(count)
  if count ~= nil and stale then label = label .. "~" end
  local color = "secondary"
  if count == nil or stale then color = "error" elseif count > 0 then color = "primary" end
  barWidget.render(ui.row({ gap = 5, align = "center" }, {
    ui.glyph({ name = "heartbeat", size = 14, color = color }),
    ui.label({ text = label, color = color, fontWeight = "bold" }),
  }))
end

noctalia.state.watch("sinity-hub.view", function(value)
  view = type(value) == "table" and value or { status = "disconnected" }
  render()
end)

function onClick()
  noctalia.togglePanel("sinity/sinnix-hub:now")
end

function update()
  render()
end
