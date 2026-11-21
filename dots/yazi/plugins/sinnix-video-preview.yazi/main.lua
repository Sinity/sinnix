local FALLBACK = require("video")
local M = {}

function M.percent(job)
	return ya.clamp(0, 10 + (job.skip or 0), 95)
end

function M:peek(job)
	local start = os.clock()
	local output = Command("media-preview-cache")
		:arg({ "ensure", tostring(job.file.path), tostring(M.percent(job)) })
		:output()

	if not output or not output.status.success then
		return FALLBACK:peek(job)
	end

	local path = output.stdout:gsub("%s+$", "")
	if path == "" then
		return FALLBACK:peek(job)
	end

	ya.sleep(math.max(0, rt.preview.image_delay / 1000 + start - os.clock()))

	local _, show_err = ya.image_show(Url(path), job.area)
	if show_err then
		return FALLBACK:peek(job)
	end

	ya.preview_widget(job, nil)
end

function M:seek(job)
	local hovered = cx.active.current.hovered
	if hovered and hovered.url == job.file.url then
		local step = ya.clamp(-1, job.units, 1)
		ya.emit("peek", { math.max(0, cx.active.preview.skip + step), only_if = job.file.url })
	end
end

function M:spot(job)
	return FALLBACK:spot(job)
end

return M
