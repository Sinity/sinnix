# aw-webui 0.13.2's Vue 2 Jest tests require vue-template-compiler, but the
# nixpkgs npm dependency set does not include it under current Node 24. Keep
# using nixpkgs' upstream ActivityWatch sources; skip only the web UI check
# phase so aw-server-rust can package the built UI.
#
# recheck: when nixpkgs bumps aw-server-rust/aw-webui past 0.13.2 — verify
# whether vue-template-compiler is present in the npm dependency set under
# the then-current Node version, or whether upstream has dropped/fixed the
# Jest check itself.
_: _final: prev: {
  aw-server-rust = prev.aw-server-rust.overrideAttrs (old: {
    env = (old.env or { }) // {
      AW_WEBUI_DIR = prev.aw-server-rust.drvAttrs.AW_WEBUI_DIR.overrideAttrs (_webuiOld: {
        doCheck = false;
      });
    };
  });
}
