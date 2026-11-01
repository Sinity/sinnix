# Codex session-lifecycle hooks: Polylogue's live hooks (`polylogue hook`)
# record every event; the shared session-start script injects one block
# (Polylogue's brief first, then acknowledged outages and recent Sinex
# sources); a pasted session ID brings its takeover context.
# Plain helper (not a NixOS module) imported directly by mcp.nix's configFn;
# the generated file is exposed via the mcp-servers.codexHooksSource option
# for tests.
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
    ];
  };
}
