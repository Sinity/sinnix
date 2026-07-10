# Registry-driven per-client MCP config generation: Codex full/lean/
# evidence/browser profiles plus the alternate-backend (deepseek/local)
# profiles, the Gemini settings.json MCP table, and the shared/Codex skill
# farms. Plain helper (not a NixOS module) — imported directly by mcp.nix's
# configFn, not picked up by auto-import.
{
  lib,
  pkgs,
  inputs,
  mcpRegistry,
  tomlFormat,
  jsonFormat,
}:
let
  inherit (mcpRegistry)
    selectClientServersForProfile
    renderCodexServer
    renderGeminiServer
    ;
  mkCodexProfileFile =
    profile:
    tomlFormat.generate "codex-${profile}-profile.toml" {
      mcp_servers = lib.mapAttrs renderCodexServer (selectClientServersForProfile profile "codex");
    };
  codexConfigFile = inputs.self + "/dots/codex/config.toml";
  codexFullConfigFile = mkCodexProfileFile "full";
  codexLeanConfigFile = mkCodexProfileFile "lean";
  codexEvidenceConfigFile = mkCodexProfileFile "evidence";
  codexBrowserConfigFile = mkCodexProfileFile "browser";
  # Alternate-backend profiles: the full MCP table plus a model + provider.
  # `codex --profile <name>` layers these over ~/.codex/config.toml, so the
  # provider's base_url/env_key and the chosen model override the gpt-5.6-sol
  # defaults while keeping the full MCP surface.
  mkCodexBackendProfileFile =
    name: extra:
    tomlFormat.generate "codex-${name}-profile.toml" (
      {
        mcp_servers = lib.mapAttrs renderCodexServer (selectClientServersForProfile "full" "codex");
      }
      // extra
    );
  codexDeepseekConfigFile = mkCodexBackendProfileFile "deepseek" {
    model = "deepseek-chat";
    model_provider = "deepseek";
    model_providers.deepseek = {
      name = "DeepSeek";
      base_url = "https://api.deepseek.com/v1";
      env_key = "DEEPSEEK_API_KEY";
    };
  };
  # Local models via the LiteLLM gateway (modules/services/litellm.nix). Keep
  # `model` in sync with that module's model_list.
  codexLocalConfigFile = mkCodexBackendProfileFile "local" {
    model = "local-llama";
    model_provider = "local";
    model_providers.local = {
      name = "Local (LiteLLM)";
      base_url = "http://127.0.0.1:4000/v1";
      env_key = "LITELLM_LOCAL_KEY";
    };
  };
  sharedSkillNames = import ../../../../flake/data/shared-agent-skills.nix;
  sharedSkillLinks = map (name: {
    inherit name;
    path = inputs.self + "/dots/_ai/skills/${name}";
  }) sharedSkillNames;
  sharedSkillFarm = pkgs.linkFarm "sinnix-shared-agent-skills" sharedSkillLinks;
  codexSkillFarm = pkgs.linkFarm "sinnix-codex-agent-skills" (
    sharedSkillLinks
    ++ [
      {
        name = ".system";
        path = inputs.self + "/dots/codex/skills/.system";
      }
    ]
  );
  geminiSettingsBase = removeAttrs (builtins.fromJSON (
    builtins.readFile (inputs.self + "/dots/gemini/settings.json")
  )) [ "mcpServers" ];
  geminiSettingsFile = jsonFormat.generate "gemini-settings.json" (
    geminiSettingsBase
    // {
      mcpServers = lib.mapAttrs renderGeminiServer (selectClientServersForProfile "full" "gemini");
    }
  );
in
{
  inherit
    codexConfigFile
    codexFullConfigFile
    codexLeanConfigFile
    codexEvidenceConfigFile
    codexBrowserConfigFile
    codexDeepseekConfigFile
    codexLocalConfigFile
    sharedSkillFarm
    codexSkillFarm
    geminiSettingsFile
    ;
}
