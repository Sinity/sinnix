{ mkFeatureTest, ... }:
mkFeatureTest {
  name = "dev-editors-antigravity";
  feature = "sinnix.features.dev.editors.enable";
  extraModules = [
    (
      { ... }:
      {
        sinnix.features.dev.editors.antigravity.enable = true;
      }
    )
  ];
  assertions =
    config:
    let
      hasAntigravityDir =
        entry:
        if builtins.isAttrs entry then
          (entry.directory or null) == ".config/Antigravity"
        else
          entry == ".config/Antigravity";
    in
    [
      {
        assertion = builtins.any hasAntigravityDir config.sinnix.persistence.home.directories;
        message = "Antigravity state must be persisted under ~/.config/Antigravity";
      }
    ];
}
