{
  lib,
  mkFeatureTest,
  hmFor,
  ...
}:
mkFeatureTest {
  name = "desktop-noctalia";
  feature = "sinnix.features.desktop.noctalia.enable";
  assertions =
    config:
    let
      hm = hmFor config;
      noctaliaConfig = hm.xdg.configFile."noctalia/config.toml" or { };
      activation = hm.home.activation.reconcileNoctaliaState.data or "";
    in
    [
      {
        assertion =
          noctaliaConfig.force == true
          && noctaliaConfig ? source
          && lib.hasSuffix "-hm_config.toml" (builtins.toString noctaliaConfig.source);
        message = "Noctalia config.toml must stay writable through the repo dotfile symlink";
      }
      {
        assertion =
          lib.hasInfix "interval_seconds" activation
          && lib.hasInfix "\${1}120" activation
          && !(lib.hasInfix "transition_on_startup" activation);
        message = "Noctalia activation must reconcile stale wallpaper automation state";
      }
    ];
}
