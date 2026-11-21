--- @sync entry
return {
	entry = function()
		local paths = {}
		for _, file in pairs(cx.active.selected) do
			paths[#paths + 1] = tostring(file.url)
		end
		if #paths == 0 then
			paths[1] = tostring(cx.active.current.cwd)
		end
		local child, err = Command("sinnix-rank-desktop"):arg("--files"):arg(paths):spawn()
		if not child then
			ya.notify({ title = "Compare", content = tostring(err), level = "error", timeout = 5 })
		end
	end,
}
