# Codex session-lifecycle hooks: Polylogue's live hooks (`polylogue hook`)
# record every event; the shared session-start script injects one block
# (Polylogue's brief first, then acknowledged outages and recent Sinex
# sources); a pasted session ID brings its takeover context. Shell commands
# pass the destructive-command guard Claude Code runs (Codex reports every
# shell tool as `Bash`). Plannotator reviews a plan when a turn ends with
# one: its Stop hook reads the turn from the transcript, exits at once when
# there is no plan, and otherwise holds the turn until the operator decides
# (the timeout is upstream's four days).
# Plain helper (not a NixOS module) imported directly by mcp.nix's configFn,
# which installs the file as /etc/codex/hooks.json; it is also exposed via the
# mcp-servers.codexHooksSource option for tests.
{ pkgs, dotsRoot }:
let
  jsonFormat = pkgs.formats.json { };
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
      {
        hooks = [
          {
            type = "command";
            command = "polylogue hook UserPromptSubmit --harness codex";
          }
        ];
      }
    ];
    PreCompact = [
      {
        hooks = [
          {
            type = "command";
            command = "polylogue hook PreCompact --harness codex";
          }
        ];
      }
    ];
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
      {
        hooks = [
          {
            type = "command";
            command = "polylogue hook PreToolUse --harness codex";
          }
        ];
      }
    ];
    PostToolUse = [
      {
        hooks = [
          {
            type = "command";
            command = "polylogue hook PostToolUse --harness codex";
          }
        ];
      }
    ];
    Stop = [
      {
        hooks = [
          {
            type = "command";
            command = "polylogue hook Stop --harness codex";
          }
        ];
      }
      {
        hooks = [
          {
            type = "command";
            command = "plannotator";
            timeout = 345600;
          }
        ];
      }
    ];
  };
}
