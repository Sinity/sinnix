# Codex session-lifecycle hooks (SessionStart/UserPromptSubmit/Stop):
# Beads/session-recall priming and Polylogue capture. Plain helper (not a NixOS
# module) imported directly by mcp.nix's
# configFn; the generated file is exposed via the mcp-servers.codexHooksSource
# option for tests.
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
            command = "bd-prime-if-present";
          }
          {
            type = "command";
            command = "${dotsRoot}/claude/hooks/sessionstart-sinex-recall.sh";
          }
          {
            type = "command";
            command = "polylogue-hook SessionStart --provider codex --sidecar-dir /home/sinity/.local/share/polylogue/hooks";
          }
        ];
      }
    ];
    UserPromptSubmit = [
      {
        hooks = [
          {
            type = "command";
            command = "bd-prime-if-present --memories-only";
          }
          {
            type = "command";
            command = "polylogue-hook UserPromptSubmit --provider codex --sidecar-dir /home/sinity/.local/share/polylogue/hooks";
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
            command = "polylogue-hook PreToolUse --provider codex --sidecar-dir /home/sinity/.local/share/polylogue/hooks";
          }
        ];
      }
    ];
    PostToolUse = [
      {
        hooks = [
          {
            type = "command";
            command = "polylogue-hook PostToolUse --provider codex --sidecar-dir /home/sinity/.local/share/polylogue/hooks";
          }
        ];
      }
    ];
    Stop = [
      {
        hooks = [
          {
            type = "command";
            command = "polylogue-hook Stop --provider codex --sidecar-dir /home/sinity/.local/share/polylogue/hooks";
          }
        ];
      }
    ];
  };
}
