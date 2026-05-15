{
  mkServiceTest,
  expect,
  hmFor,
  lib,
  ...
}:
mkServiceTest {
  name = "services-hermes";
  service = "hermes";
  assertions =
    config:
    let
      hm = hmFor config;
      configText =
        if hm.home.file.".hermes/config.yaml" ? source then
          builtins.readFile hm.home.file.".hermes/config.yaml".source
        else
          "";
    in
    [
      (expect.hmFileExists hm ".hermes/config.yaml" "Hermes config must be managed")
      (expect.hmFileExists hm ".local/bin/hermes" "Hermes wrapper must be managed")
      (expect.hmPackagedWrapper hm ".local/bin/hermes" {
        binaryFragments = [ "/bin/hermes" ];
      } "Hermes wrapper must launch the packaged Hermes binary")
      (expect.hmFileTextContainsAll hm ".local/bin/hermes" [
        "unset PYTHONPATH"
        "PYTHONNOUSERSITE=1"
        "sinnix-scope"
      ] "Hermes wrapper must sanitize Python env leakage and run in the background agent scope")
      (expect.persistedHomeDir config ".hermes" "Hermes state must be persisted under ~/.hermes")
      {
        assertion = config.sinnix.features.dev.mcp-servers.enable;
        message = "Hermes must enable the shared MCP wrapper registry by default";
      }
      (expect.textContainsAll configText [
        "default: deepseek-v4-pro"
        "provider: deepseek"
        "max_snapshots: 1000000"
        "approvals:"
        "max_turns: 1000000"
        "model: gpt-5.5"
        "cwd: /realm/project"
        "mcp_servers:"
        "context7:"
        "github:"
        "polylogue:"
        "firecrawl:"
        "playwright:"
        "command: mcp-polylogue"
        "command: mcp-firecrawl"
        "command: mcp-playwright"
        "url: https://mcp.context7.com/mcp"
        "url: https://api.githubcopilot.com/mcp/"
      ] "Hermes config must use DeepSeek V4 Pro, GPT-5.5 fallback, and shared MCP servers")
      {
        assertion = !(lib.hasInfix "deepseek-chat" configText);
        message = "Hermes config must not use the legacy deepseek-chat alias";
      }
      {
        assertion = !(lib.hasInfix "gpt-5.3-codex" configText);
        message = "Hermes fallback must not use gpt-5.3-codex";
      }
    ];
}
