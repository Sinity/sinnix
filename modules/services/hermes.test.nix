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
      (expect.hmFileExists hm ".local/bin/hermes-mirror" "Hermes mirror wrapper must be managed")
      (expect.hmFileExists hm ".local/bin/hermes-rp" "Hermes RP wrapper must be managed")
      (expect.hmFileExists hm ".local/bin/hermes-research" "Hermes research wrapper must be managed")
      (expect.hmFileExists hm ".local/bin/hermes-code" "Hermes code wrapper must be managed")
      (expect.hmPackagedWrapper hm ".local/bin/hermes" {
        binaryFragments = [ "/bin/hermes" ];
      } "Hermes wrapper must launch the packaged Hermes binary")
      (expect.hmFileTextContainsAll hm ".local/bin/hermes" [
        "unset PYTHONPATH"
        "PYTHONNOUSERSITE=1"
        "sinnix-scope"
      ] "Hermes wrapper must sanitize Python env leakage and run in the background agent scope")
      (expect.hmFileTextContainsAll hm ".local/bin/hermes-mirror" [
        "--continue \"cognitive-mirror\""
        "--skills \"cognitive-mirroring\""
        "--toolsets \"skills,memory,session_search,terminal,file,todo,delegation\""
      ] "Hermes mirror wrapper must preload mirror skill and narrowed mirror toolsets")
      (expect.hmFileTextContainsAll hm ".local/bin/hermes-rp" [
        "--continue \"cognitive-mirror-rp\""
        "--skills \"cognitive-mirroring\""
        "--toolsets \"skills,memory,session_search,file\""
      ] "Hermes RP wrapper must keep the mirror persona surface narrow")
      (expect.hmFileTextContainsAll hm ".local/bin/hermes-research" [
        "--skills \"deep-research,hermes-agent\""
        "--toolsets \"web,browser,search,delegation,file,terminal,skills\""
      ] "Hermes research wrapper must expose research tools without global bloat")
      (expect.hmFileTextContainsAll hm ".local/bin/hermes-code" [
        "--skills \"sinnix-workflows,git-conventions,hermes-agent\""
        "--toolsets \"terminal,file,github,context7,delegation,skills,todo\""
      ] "Hermes code wrapper must expose code tools without browser/RP bloat")
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
        "lynchpin:"
        "firecrawl:"
        "playwright:"
        "command: mcp-polylogue"
        "command: mcp-lynchpin"
        "LYNCHPIN_REPO_ROOT: /realm/project/sinity-lynchpin"
        "LYNCHPIN_LOCAL_ROOT: /realm/project/sinity-lynchpin/.lynchpin"
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
