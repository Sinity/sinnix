# Desktop Bundle - auto-enables all features.desktop.* plus system dependencies
#
# Uses mkBundleModule for auto-discovery of desktop features.
# Adding a new feature to features/desktop/ automatically includes it here.
{ lib, ... }@args:
lib.sinnix.mkBundleModule {
  name = "desktop";
  description = "Standard Desktop Environment Bundle";
  featureDomain = "desktop";
  extraEnables = {
    # System-level requirements for desktop
    "features.system.nix-ld" = true;
  };
} args
