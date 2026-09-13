--!nonstrict
-- Everyday activity controls, not an operations dashboard.
-- Opening and dismissing the view never change a declaration.
local activity = noctalia.state.get("sinnix-cockpit.activity")
local draftName, draftBoundary = "", ""
local notice, busy = nil, false
local editing, opened, opening = false, false, 0
local TEXT, MUTED, ACCENT, BG, CARD = "#f3f7fc", "#b8cbdc", "#7bd5ff", "#101923", "#1b2b3b"

local function quote(value)
  return "'" .. string.gsub(tostring(value or ""), "'", [=['"'"']=]) .. "'"
end
local COMMAND = quote(noctalia.expandPath("~/.local/bin/sinnix-activity")) .. " --actor desktop"

local function run(arguments)
  if busy then return end
  busy, notice = true, nil
  local startedIn = opening
  render()
  local accepted = noctalia.runAsync(COMMAND .. " " .. arguments, function(result)
    busy = false
    if result.exitCode ~= 0 or result.timedOut then
      notice = result.stderr ~= nil and result.stderr ~= "" and result.stderr or "The change could not be saved"
    else
      local ok, value = pcall(noctalia.json.decode, result.stdout)
      if ok and type(value) == "table" and value.schema == "sinnix-activity/v1" then
        noctalia.state.set("sinnix-cockpit.activity", value)
        if opened and opening == startedIn then panel.close() end
      else
        notice = "No readable receipt; check the saved state before repeating"
      end
    end
    noctalia.state.set("sinnix-cockpit.activity-refresh", noctalia.nowMs())
    if opened then render() end
  end, 15000)
  if not accepted then
    busy, notice = false, "Could not start. Your input has been kept."
    render()
  end
end

local function choose()
  if string.match(draftName, "^%s*$") then notice = "Name the activity first"; render(); return end
  local option
  if draftBoundary == "" or draftBoundary == "open-ended" then option = "--open-ended"
  elseif string.match(draftBoundary, "^[1-9]%d*[mhd]$") then option = "--for " .. quote(draftBoundary)
  else option = "--until " .. quote(draftBoundary) end
  run("choose " .. option .. " -- " .. quote(draftName))
end

local function button(label, callback, enabled, variant)
  return ui.button({ text = label, onClick = callback, enabled = enabled ~= false and not busy,
    variant = variant or "outline", controlSize = "lg" })
end

local function text(value, size, color)
  return ui.label({ text = value, fontSize = size or 16, color = color or TEXT, maxWidth = 630, maxLines = 3 })
end

local function secondaryBoundary(value)
  if value.mode == "paused" then return "Reminders paused. This activity is still saved." end
  if value.mode == "acknowledged" then return "Reconsideration acknowledged. No reminder pending." end
  if value.mode == "due" then return "The boundary has passed. Your next choice is open." end
  if value.reconsider_at == nil then return "Open-ended. No timer is running." end
  return "Reconsider at " .. (value.reconsider_local or value.reconsider_at)
end

function render()
  if not opened then return end
  local value = type(activity) == "table" and activity or {}
  local available = value.schema == "sinnix-activity/v1" and value.error == nil
  local hasActivity = available and type(value.activity) == "string"
  local rows = {
    ui.row({ align = "center", justify = "space_between" }, {
      ui.label({ text = editing and "What next?" or "Now", fontSize = 28, fontWeight = "bold", color = ACCENT }),
      button("Close", function() panel.close() end, true, "ghost"),
    }),
  }
  if editing then
    table.insert(rows, text("Name the activity. A time boundary is optional.", 17, MUTED))
    table.insert(rows, ui.input({ key = "activity-name", value = draftName, placeholder = "What are you going to do?", focus = true,
      controlSize = "lg", fontSize = 22, enabled = not busy,
      onChange = function(value) draftName = value end, onSubmit = function(value) draftName = value; choose() end }))
    table.insert(rows, ui.input({ key = "activity-boundary", value = draftBoundary, placeholder = "30m, 00:00, or leave blank for open-ended",
      controlSize = "lg", fontSize = 18, enabled = not busy,
      onChange = function(value) draftBoundary = value end, onSubmit = function(value) draftBoundary = value; choose() end }))
    table.insert(rows, text("Duration starts now. A clock time means its next local occurrence.", 13, MUTED))
    table.insert(rows, ui.row({ gap = 12 }, {
      button("Begin", choose, available, "primary"),
      button("Back", function() editing = false; render() end, true, "ghost"),
    }))
  else
    table.insert(rows, ui.column({ gap = 14, padding = 24, fill = CARD, radius = 14, border = ACCENT, borderWidth = 1 }, {
      text("LAST CHOSEN ACTIVITY", 12, ACCENT),
      text(available and (value.activity or "Nothing chosen yet") or "Activity unavailable", 30),
      text(available and secondaryBoundary(value) or (value.error or "Reading saved state…"), 16, MUTED),
    }))
    table.insert(rows, ui.row({ gap = 12 }, {
      button("Choose next", function() editing = true; render() end, available, "primary"),
      button("Return to chat", function() run("open") end, available and type(value.return_url) == "string"),
      button("Capture", function() panel.close(); noctalia.togglePanel("sinity/sinnix-cockpit:capture-panel") end),
    }))
    if hasActivity and value.reconsider_at ~= nil and value.mode ~= "paused" then
      table.insert(rows, ui.row({ gap = 8 }, {
        button("Continue 15m", function() run("extend 15m") end),
        button("Continue 60m", function() run("extend 60m") end),
        button("Mark reviewed", function() run("ack") end, value.mode ~= "acknowledged", "ghost"),
      }))
    end
    if hasActivity and (value.reconsider_at ~= nil or value.mode == "paused") then
      table.insert(rows, button(value.mode == "paused" and "Resume reminders" or "Pause reminders", function()
        run(value.mode == "paused" and "resume" or "pause")
      end, true, "ghost"))
    end
    table.insert(rows, ui.row({ gap = 12 }, {
      button("Machine status", function() panel.close(); noctalia.togglePanel("sinity/sinnix-ops:now") end, true, "ghost"),
      text("Super+F12  ·  open / close", 13, MUTED),
    }))
  end
  if busy then table.insert(rows, text("Applying…", 14, ACCENT)) end
  if notice ~= nil then table.insert(rows, text(notice, 14, "error")) end
  panel.render(ui.column({ gap = 18, padding = 28, fill = BG, radius = 18, border = ACCENT, borderWidth = 1 }, rows))
end

noctalia.state.watch("sinnix-cockpit.activity", function(value)
  activity = value
  if opened then render() end
end)

function onOpen(_context)
  opened, editing, opening = true, false, opening + 1
  render()
end

function onClose()
  opened, opening = false, opening + 1
end
