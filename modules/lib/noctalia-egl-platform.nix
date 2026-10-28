{ pkgs }:
let
  # NVIDIA 6235dd8200c52f81c55882bcaf5553715d9565cf: explicit-sync
  # buffers must not retain ignored release events on an undispatched queue.
  package = pkgs.egl-wayland2.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [
      ../features/desktop/noctalia-egl-wayland2-release-events.patch
    ];
  });
  manifest = pkgs.writeText "noctalia-egl-wayland2.json" (
    builtins.toJSON {
      file_format_version = "1.0.0";
      ICD.library_path = "${pkgs.lib.getLib package}/lib/libnvidia-egl-wayland2.so.1";
    }
  );
  files = [
    manifest
    "${pkgs.egl-wayland}/share/egl/egl_external_platform.d/10_nvidia_wayland.json"
    "${pkgs.egl-gbm}/share/egl/egl_external_platform.d/15_nvidia_gbm.json"
    "${pkgs.egl-x11}/share/egl/egl_external_platform.d/20_nvidia_xcb.json"
    "${pkgs.egl-x11}/share/egl/egl_external_platform.d/20_nvidia_xlib.json"
  ];
in
{
  inherit package manifest files;
  environment = "__EGL_EXTERNAL_PLATFORM_CONFIG_FILENAMES=${pkgs.lib.concatStringsSep ":" files}";
}
