--!nonstrict
-- Bounded polling of declared state; no observation or behavioral inference.
local polling, again = false, false
local command = "'" .. string.gsub(noctalia.expandPath("~/.local/bin/sinnix-activity"), "'", [=['"'"']=]) .. "' status --json"

local function publish(value)
  noctalia.state.set("sinnix-cockpit.activity", value)
end

local poll
poll = function()
  if polling then again = true; return end
  polling = true
  local accepted = noctalia.runAsync(command, function(result)
    polling = false
    if result.exitCode ~= 0 or result.timedOut then
      publish({ error = result.stderr ~= nil and result.stderr ~= "" and result.stderr or "Activity state is unavailable" })
    else
      local ok, value = pcall(noctalia.json.decode, result.stdout)
      if ok and type(value) == "table" and value.schema == "sinnix-activity/v1" then
        publish(value)
      else
        publish({ error = "Activity state has an unsupported schema" })
      end
    end
    if again then again = false; poll() end
  end, 15000)
  if not accepted then
    polling = false
    publish({ error = "Could not start the activity-state reader" })
  end
end

noctalia.setUpdateInterval(10000)
noctalia.state.watch("sinnix-cockpit.activity-refresh", function() poll() end)
poll()

function update()
  poll()
end
