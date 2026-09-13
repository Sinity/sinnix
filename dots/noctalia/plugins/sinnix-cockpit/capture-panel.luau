--!nonstrict
-- A literal fragment inbox. Notes never choose, finish, or acknowledge an activity.
local DRAFT = noctalia.expandPath("~/.local/state/sinnix/activity/capture-draft.txt")
local text = noctalia.readFile(DRAFT) or ""
local opened, generation, busy, errorText = false, 0, false, nil
local keyVersion = 0
local function quote(value)
  return "'" .. string.gsub(tostring(value), "'", [=['"'"']=]) .. "'"
end
local COMMAND = quote(noctalia.expandPath("~/.local/bin/sinnix-activity")) .. " --actor desktop.capture note -- "

local function keepDraft(value)
  text = value
  local ok, err = noctalia.writeFile(DRAFT .. ".tmp", value)
  if ok then ok, err = noctalia.renameFile(DRAFT .. ".tmp", DRAFT) end
  if not ok then errorText = "Draft is in memory only: " .. tostring(err or "write failed") end
end

local function save()
  if busy then return end
  if string.match(text, "^%s*$") then errorText = "A fragment is enough; blank notes are not saved."; render(); return end
  local submitted, submittedIn = text, generation
  busy, errorText = true, nil
  render()
  local accepted = noctalia.runAsync(COMMAND .. quote(submitted), function(result)
    busy = false
    local ok, receipt = pcall(noctalia.json.decode, result.stdout or "")
    if result.exitCode == 0 and not result.timedOut and ok and type(receipt) == "table"
      and type(receipt.capture) == "table" and receipt.capture.event_id ~= nil then
      if text == submitted then
        text = ""
        noctalia.removeFile(DRAFT)
        keyVersion = keyVersion + 1
      end
      if opened and generation == submittedIn then panel.close() end
    else
      errorText = result.stderr ~= nil and result.stderr ~= "" and result.stderr or "No save receipt. Your draft has been kept."
    end
    if opened then render() end
  end, 15000)
  if not accepted then busy, errorText = false, "Could not start saving. Your draft has been kept."; render() end
end

function render()
  if not opened then return end
  local rows = {
    ui.row({ justify = "space_between", align = "center" }, {
      ui.label({ text = "Catch a thought", fontSize = 27, fontWeight = "bold", color = "#7bd5ff" }),
      ui.button({ text = "Close", variant = "ghost", controlSize = "lg", onClick = function() panel.close() end }),
    }),
    ui.label({ text = "A fragment, observation, or where to resume. No classification needed.", fontSize = 16, color = "#b8cbdc", maxLines = 2 }),
    ui.input({ key = "capture-text-" .. keyVersion, value = text, placeholder = "Put it here before it disappears…", focus = true,
      multiline = true, submitOnEnter = true, height = 145, fontSize = 20, enabled = not busy,
      onChange = keepDraft, onSubmit = function(value) keepDraft(value); save() end }),
    ui.row({ gap = 14, align = "center" }, {
      ui.button({ text = busy and "Saving…" or "Save and return", variant = "primary", controlSize = "lg", enabled = not busy, onClick = save }),
      ui.label({ text = "Enter saves · Shift+Enter adds a line", fontSize = 13, color = "#b8cbdc" }),
    }),
    ui.label({ text = "Escape keeps the draft. Saving does not change your activity.", fontSize = 13, color = "#b8cbdc" }),
  }
  if errorText then table.insert(rows, ui.label({ text = errorText, color = "error", maxWidth = 630, maxLines = 2 })) end
  panel.render(ui.column({ gap = 12, padding = 24, fill = "#101923", radius = 18, border = "#7bd5ff", borderWidth = 1 }, rows))
end

function onOpen()
  opened, generation = true, generation + 1
  keyVersion = keyVersion + 1
  render()
end

function onClose()
  opened, generation = false, generation + 1
end
