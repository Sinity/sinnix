# Codex session-lifecycle hooks: Polylogue's live hooks (`polylogue internal hook`)
# record every event; the shared session-start script injects one block
# (Polylogue's brief first, then acknowledged outages and recent Sinex
# sources); a pasted session ID brings its takeover context. Shell commands
# pass the destructive-command guard Claude Code runs (Codex reports every
# shell tool as `Bash`). The attention hook raises a desktop
# notification when an attended session asks for permission or ends a turn
# longer than ten minutes; the prompt hook stamps the turn's start for it.
# Plain helper (not a NixOS module) imported directly by mcp.nix's configFn,
# which installs the file as /etc/codex/hooks.json; it is also exposed via the
# mcp-servers.codexHooksSource option for tests.
{ pkgs, dotsRoot }:
let
  jsonFormat = pkgs.formats.json { };
  attentionHook = {
    type = "command";
    command = "${dotsRoot}/claude/hooks/attention-notify.py codex";
    timeout = 3;
  };
  capture = event: {
    hooks = [
      {
        type = "command";
        command = "polylogue internal hook ${event} --harness codex";
      }
    ];
  };
in
jsonFormat.generate "codex-hooks.json" {
  hooks = {
    SessionStart = [
      {
        matcher = "startup|resume";
        hooks = [
          {
            type = "command";
            command = "${dotsRoot}/claude/hooks/sessionstart-context.sh codex";
          }
        ];
      }
    ];
    UserPromptSubmit = [
      (capture "UserPromptSubmit")
      { hooks = [ attentionHook ]; }
    ];
    PermissionRequest = [
      (capture "PermissionRequest")
      { hooks = [ attentionHook ]; }
    ];
    PreCompact = [ (capture "PreCompact") ];
    PreToolUse = [
      {
        matcher = "^Bash$";
        hooks = [
          {
            type = "command";
            command = "${dotsRoot}/claude/hooks/pretooluse-bash.py codex";
            timeout = 3;
          }
        ];
      }
      (capture "PreToolUse")
    ];
    PostToolUse = [ (capture "PostToolUse") ];
    SessionEnd = [ (capture "SessionEnd") ];
    SubagentStart = [ (capture "SubagentStart") ];
    SubagentStop = [ (capture "SubagentStop") ];
    Stop = [
      (capture "Stop")
      { hooks = [ attentionHook ]; }
    ];
  };
}
