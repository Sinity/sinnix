# Codex session-lifecycle hooks (SessionStart/UserPromptSubmit/Stop):
# Session recall and Polylogue capture. Plain helper (not a NixOS module)
# imported directly by mcp.nix's
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
            command = "${dotsRoot}/claude/hooks/sessionstart-sinex-recall.sh";
          }
          {
            type = "command";
            command = "polylogue-hook SessionStart --provider codex";
          }
        ];
      }
    ];
    UserPromptSubmit = [
      {
        hooks = [
          {
            type = "command";
            command = "polylogue-hook UserPromptSubmit --provider codex";
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
        # Codex 0.154 exposes spawn_agent through PreToolUse. The guard
        # validates request intent only; it cannot observe child resolution.
        matcher = "^spawn_agent$";
        hooks = [
          {
            type = "command";
            command = "${dotsRoot}/claude/hooks/pretooluse-agent-model.sh";
            timeout = 5;
          }
        ];
      }
      {
        hooks = [
          {
            type = "command";
            command = "polylogue-hook PreToolUse --provider codex";
          }
        ];
      }
    ];
    PostToolUse = [
      {
        hooks = [
          {
            type = "command";
            command = "polylogue-hook PostToolUse --provider codex";
          }
        ];
      }
    ];
    Stop = [
      {
        hooks = [
          {
            type = "command";
            command = "polylogue-hook Stop --provider codex";
          }
        ];
      }
    ];
  };
}
