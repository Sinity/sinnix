# Codex session-lifecycle hooks (SessionStart/UserPromptSubmit/Stop):
# Session recall and Polylogue capture. Plain helper (not a NixOS module)
# imported directly by mcp.nix's
# configFn; the generated file is exposed via the mcp-servers.codexHooksSource
# option for tests.
{ pkgs, dotsRoot, dataDir }:
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
            command = "polylogue-hook SessionStart --provider codex --sidecar-dir ${dataDir}/hooks";
          }
        ];
      }
    ];
    UserPromptSubmit = [
      {
        hooks = [
          {
            type = "command";
            command = "polylogue-hook UserPromptSubmit --provider codex --sidecar-dir ${dataDir}/hooks";
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
            command = "polylogue-hook PreToolUse --provider codex --sidecar-dir ${dataDir}/hooks";
          }
        ];
      }
    ];
    PostToolUse = [
      {
        hooks = [
          {
            type = "command";
            command = "polylogue-hook PostToolUse --provider codex --sidecar-dir ${dataDir}/hooks";
          }
        ];
      }
    ];
    Stop = [
      {
        hooks = [
          {
            type = "command";
            command = "polylogue-hook Stop --provider codex --sidecar-dir ${dataDir}/hooks";
          }
        ];
      }
    ];
  };
}
