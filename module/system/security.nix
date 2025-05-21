{
  pkgs,
  config,
  lib,
  ...
}:
let
  # Find all .age files in the secret directory
  secretFiles = lib.filterAttrs (name: _: lib.hasSuffix ".age" name) (builtins.readDir ../../secret);
in
{
  # Combined security configuration
  security = {
    rtkit.enable = true;
    sudo.wheelNeedsPassword = false;
    pam.services.hyprlock = { };
    wrappers.bubblewrap = {
      source = "${pkgs.bubblewrap}/bin/bwrap";
      owner = "root";
      group = "root";
      setuid = true;
    };
  };

  # Other security-related settings
  networking.firewall.enable = false;
  services.gnome.gnome-keyring.enable = true;

  # Authentication agent
  programs.gnupg.agent = {
    enable = true;
    enableSSHSupport = true;
    # pinentryFlavor = "";
  };

  # For claude-desktop-with-fhs to run
  boot.kernel.sysctl."kernel.unprivileged_userns_clone" = 1;

  # Secret management
  age = {
    identityPaths = [ "/home/sinity/.ssh/id_ed25519" ];

    # Automatically create secret configs for all .age files
    secrets = lib.mapAttrs' (filename: _: {
      # Secret names don't include the .age extension
      name = lib.removeSuffix ".age" filename;
      # Config for this secret
      value = {
        # Full path to the secret file
        file = ../../secret/${filename};
        owner = "sinity";
      };
    }) secretFiles;
  };

  # Set environment variables for all secrets
  programs.zsh.loginShellInit = lib.concatStringsSep "\n" (
    lib.mapAttrsToList (
      filename: _:
      let
        # Secret name without .age extension (matches the name above)
        secretName = lib.removeSuffix ".age" filename;
        # Convert to environment variable format: UPPERCASE_WITH_UNDERSCORES
        envName = lib.toUpper (lib.replaceStrings [ "-" ] [ "_" ] secretName);
        # Point to the path where agenix places the decrypted secret
      in
      ''export ${envName}="$(<${config.age.secrets.${secretName}.path})"''
    ) secretFiles
  );
}
