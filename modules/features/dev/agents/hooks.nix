# Codex session-lifecycle hooks (SessionStart/UserPromptSubmit/Stop):
# session recall, and Polylogue's live hooks (`polylogue-live hook`): its
# session-start brief, takeovers of pasted session IDs and live state.
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
            command = "${dotsRoot}/claude/hooks/sessionstart-sinex-recall.sh";
          }
          {
            type = "command";
            command = "polylogue-live hook SessionStart --harness codex";
          }
        ];
      }
    ];
    UserPromptSubmit = [
      {
        hooks = [
          {
            type = "command";
            command = "polylogue-live hook UserPromptSubmit --harness codex";
          }
        ];
      }
    ];
    PreCompact = [
      {
        hooks = [
          {
            type = "command";
            command = "sinnix-context-handoff";
          }
        ];
      }
    ];
    PreToolUse = [
      {
        hooks = [
          {
            type = "command";
            command = "polylogue-live hook PreToolUse --harness codex";
          }
        ];
      }
    ];
    PostToolUse = [
      {
        hooks = [
          {
            type = "command";
            command = "polylogue-live hook PostToolUse --harness codex";
          }
        ];
      }
    ];
    Stop = [
      {
        hooks = [
          {
            type = "command";
            command = "polylogue-live hook Stop --harness codex";
          }
        ];
      }
    ];
  };
}
