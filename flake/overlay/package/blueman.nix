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
