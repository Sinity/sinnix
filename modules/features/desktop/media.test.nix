{
  mkFeatureTest,
  hmFor,
  ...
}:
mkFeatureTest {
  name = "desktop-media";
  feature = "sinnix.features.desktop.media.enable";
  assertions =
    config:
    let
      hm = hmFor config;
      mpv = hm.programs.mpv.config;
    in
    [
      {
        assertion = hm.programs.mpv.enable;
        message = "mpv must be enabled";
      }
      {
        assertion = mpv.fs == true && mpv.force-window == "yes";
        message = "mpv must open fullscreen without mapping an empty fullscreen window immediately";
      }
      {
        assertion = mpv."drm-vrr-enabled" == "no" && mpv."wayland-content-type" == "none";
        message = "mpv must avoid compositor/display metadata that can retrigger display blanking";
      }
    ];
}
