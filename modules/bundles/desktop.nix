# Desktop Bundle - auto-enables all features.desktop.* plus system dependencies
#
# Uses mkBundleModule for auto-discovery of desktop features.
# Adding a new feature to features/desktop/ automatically includes it here,
# except for explicitly opt-in features that would otherwise make ordinary
# desktop rebuilds or logins unexpectedly heavy.
{ lib, ... }@args:
lib.sinnix.mkBundleModule {
  name = "desktop";
  description = "Standard Desktop Environment Bundle";
  featureDomain = "desktop";
  excludeFeatures = [
    "agentVerifyTimer"
    "audioCapture"
    "hyprlandAnimations"
  ];
  extraEnables = {
    # System-level requirements for desktop
    "features.system.nix-ld" = true;
  };
} args
