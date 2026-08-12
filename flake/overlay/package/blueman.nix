# recheck: when nixpkgs's obex_data_server ships its D-Bus activation file
# already named org.openobex.service (verified 2026-08-12: stock 0.4.6 still
# ships the misnamed obex-data-server.service, and D-Bus activation looks
# the file up by bus name, so the rename is load-bearing for OBEX receive),
# or if the session stops honoring /etc/xdg/autostart (verified 2026-08-12:
# xdg-desktop-autostart.target is ACTIVE here via systemd's generator, and
# blueman-applet is already launched deliberately by the session -- without
# the autostart removal a duplicate applet starts at every login). Both
# halves are deliberate permanent policy with the above as their concrete
# recheck conditions.
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
