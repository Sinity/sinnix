{ mkFeatureTest, expect, hmFor, ... }:
mkFeatureTest {
  name = "dev-git";
  feature = "sinnix.features.dev.git.enable";
  assertions =
    config:
    let
      hm = hmFor config;
      gitSettings = hm.programs.git.settings;
      ignoreGlobal = hm.home.file.".config/git/ignore_global".text or "";
      githubHelper = gitSettings."credential \"https://github.com\"".helper or "";
    in
    [
      (expect.hmFileExists hm ".config/git/ignore_global"
        "Git feature must manage the global ignore file"
      )
      (expect.textContains ignoreGlobal "AGENTS.md"
        "Git global ignore must suppress generated AGENTS files by default"
      )
      (expect.mkAssertion (
        (gitSettings.init.defaultBranch or null) == "master"
      ) "Git must retain the canonical default branch name")
      (expect.mkAssertion (
        (gitSettings.merge.conflictStyle or null) == "zdiff3"
      ) "Git must use zdiff3 conflict markers")
      (expect.mkAssertion ((gitSettings.pull.rebase or false) == true) "Git pulls must default to rebase")
      (expect.mkAssertion (
        (gitSettings.rerere.enabled or false) == true
      ) "Git must enable rerere for repeated conflict reuse")
      (expect.textContains githubHelper "/run/agenix/github-token"
        "GitHub credential helper must read from the managed agenix token path"
      )
      (expect.mkAssertion (hm.programs.delta.enableGitIntegration or false
      ) "Delta must stay wired through git integration")
    ];
}
