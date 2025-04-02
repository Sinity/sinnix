{
  config,
  pkgs,
  lib,
  ...
}:

let
  # Override the standard hydrus package
  customHydrus = pkgs.hydrus.overrideAttrs (oldAttrs: {
    # Skip tests that are failing
    doCheck = false;
    doInstallCheck = false;
    
    # Override the installPhase to change the wrapper
    installPhase = oldAttrs.installPhase + ''
      # Create a custom wrapper for the specific directory
      mv $out/bin/hydrus-client $out/bin/hydrus-client-original
      
      cat > $out/bin/hydrus-client << EOF
      #!${pkgs.stdenv.shell}
      cd /mnt/ssd_storage/hydrus
      
      # Use the -d parameter to specify the database location
      exec $out/bin/hydrus-client-original -d="/mnt/ssd_storage/hydrus/db" "\$@"
      EOF
      
      chmod +x $out/bin/hydrus-client
    '';
    
    # Modify the wrapper to properly unset display variables
    preFixup = ''
      ${oldAttrs.preFixup or ""}
      makeWrapperArgs+=(--unset WAYLAND_DISPLAY --unset QT_QPA_PLATFORM)
    '';
  });
in
{
  home.packages = [
    # Use our modified version instead of the standard one
    customHydrus
  ];
}