"""Execute plugin callbacks against a synthetic host; real native load is a separate smoke test."""

import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import tomllib

ROOT = Path(__file__).parents[2]
PLUGIN = ROOT / "dots/noctalia/plugins/sinnix-cockpit"
LUAU = os.environ.get("LUAU_BIN") or shutil.which("luau")
STUB = r"""
local commands, callbacks, watches = {}, {}, {}
local tree, tooltip, toggled, interval, published
local sample = {schema="sinnix-activity/v1", mode="active", activity="reading", reconsider_at="2026-01-10T23:00:00Z", reconsider_local="2026-01-11 00:00 CET", return_url="https://example.test"}
local reject = false
ui = setmetatable({}, {__index=function(_, kind) return function(props, children) return {kind=kind, props=props or {}, children=children or {}} end end})
panel = {render=function(value) tree=value end, close=function() if onClose then onClose() end end}
barWidget = {render=function(value) tree=value end, setTooltip=function(value) tooltip=value end}
noctalia = {
  expandPath=function(path) return string.gsub(path, "^~", "/tmp/synthetic user's home") end,
  nowMs=function() return 10 end,
  setUpdateInterval=function(value) interval=value end,
  togglePanel=function(value) toggled=value end,
  runAsync=function(command, callback, timeout) table.insert(commands, command); table.insert(callbacks, callback); return not reject end,
  json={decode=function(_) return sample end},
  state={get=function(_) return sample end, set=function(key,value) published=value; if watches[key] then watches[key](value) end end,
         watch=function(key,callback) watches[key]=callback end},
}
local function find(kind, prop, value, node)
  node=node or tree
  if node.kind==kind and node.props[prop]==value then return node end
  for _,child in ipairs(node.children) do local match=find(kind,prop,value,child); if match then return match end end
  return nil
end
"""


@unittest.skipUnless(LUAU, "Luau interpreter required")
class ActivityDesktopTests(unittest.TestCase):
    def run_lua(self, source, assertion):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.luau"
            path.write_text(
                STUB + "\n" + (PLUGIN / source).read_text() + "\n" + assertion
            )
            result = subprocess.run(
                [LUAU, str(path)], text=True, capture_output=True, timeout=10
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_open_and_poll_do_not_issue_mutations(self):
        self.run_lua(
            "activity-panel.luau",
            """
          onOpen(); assert(#commands==0)
          watches["sinnix-cockpit.activity"](sample); assert(#commands==0)
          find("button","text","Choose next").props.onClick()
          find("input","key","activity-name").props.onChange("rest"); assert(#commands==0)
        """,
        )

    def test_quoted_name_survives_shell_roundtrip_and_busy_is_guarded(self):
        value = 'reader\'s $(printf PWNED); & "quoted" — leisure'
        output = self.run_lua(
            "activity-panel.luau",
            """
          onOpen(); find("button","text","Choose next").props.onClick()
          find("input","key","activity-name").props.onChange([==["""
            + value
            + """]==])
          find("input","key","activity-boundary").props.onChange("15m")
          local submit=find("button","text","Begin").props.onClick
          submit(); submit(); assert(#commands==1); print(commands[1])
        """,
        )
        self.assertEqual(
            shlex.split(output),
            [
                "/tmp/synthetic user's home/.local/bin/sinnix-activity",
                "--actor",
                "desktop",
                "choose",
                "--for",
                "15m",
                "--",
                value,
            ],
        )

    def test_enter_submits_clock_boundary(self):
        output = self.run_lua(
            "activity-panel.luau",
            """
          onOpen(); find("button","text","Choose next").props.onClick(); find("input","key","activity-name").props.onChange("rest")
          find("input","key","activity-boundary").props.onSubmit("00:00")
          assert(#commands==1); print(commands[1])
        """,
        )
        self.assertEqual(
            shlex.split(output)[-5:], ["choose", "--until", "00:00", "--", "rest"]
        )

    def test_open_is_not_ack_and_checkin_is_ack(self):
        output = self.run_lua(
            "activity-panel.luau",
            """
          onOpen(); find("button","text","Return to chat").props.onClick()
          assert(#commands==1); print(commands[1])
          callbacks[1]({exitCode=0, stdout="{}"})
          onOpen(); find("button","text","Mark reviewed").props.onClick(); print(commands[2])
        """,
        ).splitlines()
        self.assertEqual([shlex.split(line)[-1] for line in output], ["open", "ack"])

    def test_empty_state_disables_activity_specific_actions(self):
        self.run_lua(
            "activity-panel.luau",
            """
          sample={schema="sinnix-activity/v1", mode="unallocated"}
          watches["sinnix-cockpit.activity"](sample); onOpen()
          for _,label in ipairs({"Continue 15m","Mark reviewed","Pause reminders"}) do
            assert(find("button","text",label)==nil, label)
          end
          assert(not find("button","text","Return to chat").props.enabled)
        """,
        )

    def test_widget_retains_unicode_and_shows_clock(self):
        self.run_lua(
            "activity.luau",
            """
          sample.activity="A long multilingual activity — żółw 🐢"
          watches["sinnix-cockpit.activity"](sample)
          assert(find("label","text",sample.activity))
          assert(find("label","text","· 00:00"))
          assert(#commands==0); onClick()
          assert(toggled=="sinity/sinnix-cockpit:activity-panel")
        """,
        )

    def test_reader_only_polls_status_and_coalesces_refresh(self):
        output = self.run_lua(
            "activity-service.luau",
            """
          assert(#commands==1); update(); update(); assert(#commands==1)
          callbacks[1]({exitCode=0, stdout="{}"}); assert(#commands==2)
          print(commands[1]); assert(interval==10000)
        """,
        )
        self.assertEqual(shlex.split(output)[-2:], ["status", "--json"])

    def test_reader_errors_are_visible(self):
        self.run_lua(
            "activity-service.luau",
            """
          callbacks[1]({exitCode=1, stderr="synthetic failure"})
          assert(published.error=="synthetic failure")
          reject=true; update(); assert(published.error=="Could not start the activity-state reader")
        """,
        )


class ActivityManifestTests(unittest.TestCase):
    def test_unique_entries_and_declared_surface(self):
        manifest = tomllib.loads((PLUGIN / "plugin.toml").read_text())
        identifiers = [
            entry["id"]
            for kind in ("widget", "service", "panel")
            for entry in manifest.get(kind, [])
        ]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertIn(
            "sinity/sinnix-cockpit:activity",
            (ROOT / "dots/noctalia/config.toml").read_text(),
        )
        self.assertIn(
            "panel-toggle sinity/sinnix-cockpit:activity-panel",
            (ROOT / "modules/features/desktop/hyprland/bindings.nix").read_text(),
        )


@unittest.skipUnless(LUAU, "Luau interpreter required")
class CaptureControlTests(unittest.TestCase):
    def evaluate(self, assertions):
        extra = r"""
local memory, closeCount = {}, 0
noctalia.readFile=function(p) return memory[p] end
noctalia.writeFile=function(p,t) memory[p]=t; return true end
noctalia.renameFile=function(a,b) memory[b]=memory[a]; memory[a]=nil; return true end
noctalia.removeFile=function(p) memory[p]=nil; return true end
panel.close=function() closeCount=closeCount+1; onClose() end
"""
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "capture.luau"
            script.write_text(
                STUB
                + extra
                + (PLUGIN / "capture-panel.luau").read_text()
                + "\n"
                + assertions
            )
            result = subprocess.run(
                [LUAU, str(script)], text=True, capture_output=True, timeout=10
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_open_type_and_dismiss_only_preserve_draft(self):
        self.evaluate("""
          onOpen(); local input=find("input","key","capture-text-1")
          assert(input.props.focus); input.props.onChange("half a thought")
          onClose(); onOpen(); assert(#commands==0)
          assert(find("input","key","capture-text-2").props.value=="half a thought")
          assert(memory["/tmp/synthetic user's home/.local/state/sinnix/activity/capture-draft.txt"]=="half a thought")
        """)

    def test_capture_dispatches_only_note(self):
        output = self.evaluate("""
          onOpen(); find("input","key","capture-text-1").props.onSubmit("a fragment")
          assert(#commands==1); print(commands[1])
        """)
        self.assertEqual(shlex.split(output)[-3:], ["note", "--", "a fragment"])

    def test_failure_retains_draft(self):
        self.evaluate("""
          onOpen(); find("input","key","capture-text-1").props.onSubmit("a fragment")
          callbacks[1]({exitCode=1,stderr="synthetic failure"})
          assert(closeCount==0)
          assert(find("input","key","capture-text-1").props.value=="a fragment")
        """)

    def test_receipt_clears_draft_and_closes(self):
        self.evaluate("""
          onOpen(); find("input","key","capture-text-1").props.onSubmit("a fragment")
          sample={capture={event_id=7}}; callbacks[1]({exitCode=0,stdout="receipt"})
          assert(closeCount==1)
          assert(memory["/tmp/synthetic user's home/.local/state/sinnix/activity/capture-draft.txt"]==nil)
        """)

    def test_late_receipt_does_not_close_reopened_panel(self):
        self.evaluate("""
          onOpen(); find("input","key","capture-text-1").props.onSubmit("a fragment")
          onClose(); onOpen(); sample={capture={event_id=7}}
          callbacks[1]({exitCode=0,stdout="receipt"}); assert(closeCount==0)
        """)

    def test_busy_does_not_resubmit(self):
        self.evaluate("""
          onOpen(); find("input","key","capture-text-1").props.onChange("a fragment")
          local submit=find("button","text","Save and return").props.onClick
          submit(); submit(); assert(#commands==1)
        """)


if __name__ == "__main__":
    unittest.main()
