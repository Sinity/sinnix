{
  mkFeatureTest,
  expect,
  hmFor,
  ...
}:
mkFeatureTest {
  name = "dev-git";
  feature = "sinnix.features.dev.git.enable";
  assertions =
    config:
    let
      hm = hmFor config;
      gitSettings = hm.programs.git.settings;
    in
    [
      (expect.hmFileExists hm ".config/git/ignore_global"
        "Git feature must manage the global ignore file"
      )
      (expect.mkAssertion (
        (gitSettings.alias.cleanup or null) == "!~/.local/bin/git-cleanup-merged-pr-branches"
      ) "Git cleanup must route through the merged-PR cleanup helper")
    ];
}
