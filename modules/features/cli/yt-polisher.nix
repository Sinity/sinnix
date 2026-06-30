{
  mkFeatureModule,
  pkgs,
  inputs,
  ...
}@args:
mkFeatureModule {
  path = [
    "cli"
    "yt-polisher"
  ];
  description = "yt-polisher: English YT video → hard-burned Polish karaoke subs → unlisted upload";
  configFn =
    {
      user,
      pkgs,
      ...
    }:
    {
      home-manager.users.${user} = _: {
        home.packages = [
          pkgs.yt-polisher
        ];
      };
    };
} args
