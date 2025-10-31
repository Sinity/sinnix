{
  inputs,
  ...
}:
{
  xdg.configFile = {
    "Zed/settings.json".source = "${inputs.self}/dots/zed/settings.json";
    "Zed/keymap.json".source = "${inputs.self}/dots/zed/keymap.json";
  };
}
