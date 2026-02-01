# Dev Bundle - auto-enables all features.dev.* plus CLI core
#
# Uses mkBundleModule for auto-discovery of dev features.
# Adding a new feature to features/dev/ automatically includes it here.
{ lib, ... }@args:
lib.sinnix.mkBundleModule {
  name = "dev";
  description = "Standard Development Environment (CLI)";
  featureDomain = "dev";
  # Editors have subfeatures that default to off, so enabling base is harmless
  # but explicit exclusion keeps the bundle focused on CLI dev environment
  excludeFeatures = [ "editors" ];
  extraEnables = {
    # CLI tools are part of dev workflow
    "features.cli.core" = true;
  };
} args
