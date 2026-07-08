# recheck: unknown — needs manual audit. The D-Bus service rename
# (obex-data-server.service -> org.openobex.service) and the removed
# blueman.desktop autostart entry both look like permanent Sinnix policy
# rather than a temporary upstream-bug workaround, but that hasn't been
# confirmed against nixpkgs' obex_data_server/blueman packaging history or
# any upstream issue — a search for an open nixpkgs issue/PR renaming the
# D-Bus service file turned up nothing relevant. Needs someone to check
# whether nixpkgs' obex_data_server ever ships the service file already
# named org.openobex.service, and whether blueman's autostart entry is
# ever made conditional upstream, before this can get a real condition (or
# be marked "no recheck needed — permanent policy").
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
