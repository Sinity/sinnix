# Codex session-lifecycle hooks (SessionStart/UserPromptSubmit/Stop): orphan
# process reaping, Serena activation/cleanup, and beads/session-recall
# priming. Plain helper (not a NixOS module) — imported directly by mcp.nix's
# configFn; the generated file is exposed via the mcp-servers.codexHooksSource
# option for tests.
{ pkgs }:
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
            command = "sinnix-mcp-sweep --orphans-only --quiet";
          }
          {
            type = "command";
            command = ''
              case "''${SINNIX_CODEX_PROFILE:-full}" in
                full|browser|deepseek|local) serena-hooks activate --client=codex ;;
              esac
            '';
          }
          {
            type = "command";
            command = "bd-prime-if-present";
          }
          {
            type = "command";
            command = "sessionstart-sinex-recall";
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
            command = "bd-prime-if-present --memories-only";
          }
          {
            type = "command";
            command = "polylogue-hook UserPromptSubmit --provider codex";
          }
        ];
      }
    ];
    PreToolUse = [
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
            command = "sinnix-mcp-sweep --orphans-only --quiet";
          }
          {
            type = "command";
            command = ''
              case "''${SINNIX_CODEX_PROFILE:-full}" in
                full|browser|deepseek|local) serena-hooks cleanup --client=codex ;;
              esac
            '';
          }
          {
            type = "command";
            command = "polylogue-hook Stop --provider codex";
          }
        ];
      }
    ];
  };
}
