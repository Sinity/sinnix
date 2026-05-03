{ mkBundleTest, hmFor, ... }:
mkBundleTest {
  name = "bundle-dev";
  bundle = "dev";
  assertions =
    config:
    let
      hm = hmFor config;
    in
    [
      {
        assertion = hm.programs.zsh.enable;
        message = "Dev bundle must enable zsh";
      }
      {
        assertion = hm.programs.git.enable;
        message = "Dev bundle must enable git";
      }
      {
        assertion = hm.programs.tmux.enable;
        message = "Dev bundle must enable tmux";
      }
    ];
}
