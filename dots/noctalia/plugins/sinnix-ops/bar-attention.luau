--!nonstrict
-- Agent-attention badge. The capability behind the retired SUPER+A bind as a
-- permanently visible bar surface: pending count at a glance, urgency in the
-- color, click focuses the oldest waiting agent. Consumes only the shared
-- bridge state; the click posts the same typed reducer action that
-- `sinnix-attention` sends, with the same idempotency key, so the two entry
-- points dedupe against each other.

local ENDPOINT = noctalia.getConfig("endpoint") or "http://127.0.0.1:3090"
local TOKEN_PATH = noctalia.getConfig("token_path") or "$XDG_RUNTIME_DIR/sinnix/ops.token"
local ACTIONS_PATH = ENDPOINT .. "/v1/actions"

local view = noctalia.state.get("sinity-ops.view") or { status = "disconnected" }

local function tokenPath()
  local runtime = noctalia.getenv("XDG_RUNTIME_DIR") or ""
  return noctalia.expandPath(TOKEN_PATH:gsub("%$XDG_RUNTIME_DIR", runtime))
end

local function token()
  local raw = noctalia.readFile(tokenPath())
  if raw == nil then return nil end
  return raw:gsub("%s+$", "")
end

local function attention()
  local snapshot = view.snapshot
  if type(snapshot) ~= "table" or type(snapshot.state) ~= "table" then return nil end
  local value = snapshot.state.attention
  if type(value) ~= "table" then return nil end
  return value
end

local function pendingItems()
  local value = attention()
  if value == nil or type(value.pending) ~= "table" then return nil end
  return value.pending
end

local function isStaleView()
  return view.status == "stale" or view.status == "source-stale"
end

local function urgencyColor(items)
  for _, item in ipairs(items) do
    if item.state == "waiting_approval" or item.state == "waiting_user" then
      return "error"
    end
  end
  return "tertiary"
end

local function tooltipText(items)
  if items == nil then return "Agent attention: bridge unavailable" end
  if #items == 0 then return "No agents waiting" end
  local oldest = items[1]
  local head = tostring(#items) .. " waiting - oldest: " .. tostring(oldest.summary or oldest.state)
  local provider = oldest.provider and (" (" .. tostring(oldest.provider) .. ")") or ""
  local when = oldest.occurred_at and ("\nsince " .. tostring(oldest.occurred_at)) or ""
  return head .. provider .. when .. "\nclick: focus oldest - right-click: ops panel"
end

local function render()
  local items = pendingItems()
  local children = {}
  if items == nil then
    table.insert(children, ui.glyph({ name = "support_agent", size = 14, color = "on_surface_variant" }))
    table.insert(children, ui.label({ text = "?", color = "on_surface_variant" }))
  elseif #items == 0 then
    table.insert(children, ui.glyph({ name = "support_agent", size = 14, color = "on_surface_variant" }))
  else
    local color = isStaleView() and "secondary" or urgencyColor(items)
    table.insert(children, ui.glyph({ name = "notification_important", size = 14, color = color }))
    local suffix = isStaleView() and "!" or ""
    table.insert(children, ui.label({ text = tostring(#items) .. suffix, color = color, fontWeight = "bold" }))
  end
  barWidget.setTooltip(tooltipText(items))
  barWidget.render(ui.row({ gap = 4, align = "center" }, children))
end

function onClick()
  local items = pendingItems()
  if items == nil or #items == 0 then
    noctalia.togglePanel("sinity/sinnix-ops:now")
    return
  end
  local oldest = items[1]
  if type(oldest.job_id) ~= "string" or type(oldest.event_id) ~= "string" then
    noctalia.notifyError("Attention item is malformed; opening the ops panel instead")
    noctalia.togglePanel("sinity/sinnix-ops:now")
    return
  end
  local bearer = token()
  if bearer == nil or bearer == "" then
    noctalia.notifyError("Ops capability token unavailable; cannot focus the agent")
    return
  end
  local body = noctalia.json.encode({
    action = "focus",
    target = { job_id = oldest.job_id },
    expected_revision = view.snapshot and view.snapshot.sequence or nil,
    idempotency_key = "attention-focus:" .. oldest.event_id,
    operator_reason = "attention badge click",
  })
  noctalia.http({
    url = ACTIONS_PATH,
    method = "POST",
    body = body,
    headers = {
      "Authorization: Bearer " .. bearer,
      "Content-Type: application/json",
      "Accept: application/json",
    },
  }, function(response)
    if not response.ok or response.status < 200 or response.status >= 300 then
      noctalia.notifyError("Attention focus failed (status " .. tostring(response.status) .. ")")
    end
  end)
end

function onRightClick()
  noctalia.togglePanel("sinity/sinnix-ops:now")
end

noctalia.state.watch("sinity-ops.view", function(value)
  view = type(value) == "table" and value or { status = "disconnected" }
  render()
end)

function update()
  render()
end
