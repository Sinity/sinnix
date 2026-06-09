# aw-webui 0.13.2's Vue 2 Jest tests require vue-template-compiler, but the
# nixpkgs npm dependency set does not include it under current Node 24. Keep
# using nixpkgs' upstream ActivityWatch sources; skip only the web UI check
# phase so aw-server-rust can package the built UI.
{ ... }:
_final: prev: {
  aw-server-rust = prev.aw-server-rust.overrideAttrs (old: {
    env = (old.env or { }) // {
      AW_WEBUI_DIR = prev.aw-server-rust.drvAttrs.AW_WEBUI_DIR.overrideAttrs (_webuiOld: {
        doCheck = false;
      });
    };
  });
}
