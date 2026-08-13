# Two deliberate, permanent workarounds:
#   - obex_data_server 0.4.6 ships its D-Bus activation file misnamed as
#     obex-data-server.service; activation looks the file up by bus name, so
#     the rename to org.openobex.service is load-bearing for OBEX receive.
#   - xdg-desktop-autostart.target is active here via systemd's generator and
#     the session already launches blueman-applet deliberately, so without
#     the autostart removal a duplicate applet starts at every login.
#
# recheck: when nixpkgs's obex_data_server ships the correctly named
# activation file, or if the session stops honoring /etc/xdg/autostart.
_: final: prev:
let
  fixedObexDataServer = prev.obex_data_server.overrideAttrs (old: {
    postInstall = (old.postInstall or "") + ''
      if [ -e "$out/share/dbus-1/services/obex-data-server.service" ]; then
        mv "$out/share/dbus-1/services/obex-data-server.service" \
          "$out/share/dbus-1/services/org.openobex.service"
      fi
    '';
    passthru = (old.passthru or { }) // {
      sinnixRenamesDbusActivation = true;
    };
  });
in
{
  obex_data_server = fixedObexDataServer;
  blueman = prev.blueman.overrideAttrs (old: {
    postInstall = (old.postInstall or "") + ''
      rm -f "$out/etc/xdg/autostart/blueman.desktop"
    '';
    propagatedUserEnvPkgs = map (
      pkg: if final.lib.getName pkg == "obex-data-server" then fixedObexDataServer else pkg
    ) (old.propagatedUserEnvPkgs or [ ]);
    passthru = (old.passthru or { }) // {
      sinnixRemovesXdgAutostart = true;
      sinnixUsesRenamedObexActivation = true;
    };
  });
}
