{
  lib,
  mkFeatureTest,
  inputs,
  ...
}:
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
      editorsModule = builtins.readFile (inputs.self + "/modules/features/dev/editors.nix");
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
      {
        assertion =
          lib.hasInfix "--disable-features=WaylandWpColorManagerV1" editorsModule
          && !(lib.hasInfix "DefaultANGLEVulkan" editorsModule)
          && !(lib.hasInfix "--disable-features=WaylandWpColorManagerV1,Vulkan" editorsModule);
        message = "Editor Wayland flags must not suppress Vulkan or ANGLE Vulkan";
      }
    ];
}
