# aw-webui 0.13.2's Vue 2 Jest tests require vue-template-compiler, but the
# nixpkgs npm dependency set does not include it under current Node 24. Keep
# using nixpkgs' upstream ActivityWatch sources; skip only the web UI check
# phase so aw-server-rust can package the built UI.
#
# recheck: when nixpkgs bumps aw-server-rust/aw-webui past 0.13.2 — verify
# whether vue-template-compiler is present in the npm dependency set under
# the then-current Node version, or whether upstream has dropped/fixed the
# Jest check itself.
#
# aw-server-rust's datastore worker thread panics on ANY commit error
# (nixpkgs 0.13.2 pins aw-server-rust @656f3c9, from Oct 2024), including a
# single transient SQLITE_BUSY. Rust's std::sync::Mutex poisons permanently
# on a panicked holder, so every subsequent request 504s until a manual
# restart -- confirmed live 2026-08-09..2026-08-12 (sinnix-l3kl, ~3-day
# silent outage, systemd reported the unit healthy throughout). Upstream
# fixed exactly this in aw-server-rust@9a8802a ("handle commit failures
# gracefully instead of panicking", 2026-03-05, closes
# ActivityWatch/aw-server-rust#256) by logging and continuing instead of
# panicking on both the legacy-import commit and the main work-loop commit.
# That fix isn't in any tagged activitywatch release yet (only unreleased
# 0.14.0 betas built after 2026-05); backport it directly as a vendored
# patch until nixpkgs bumps past a release that includes it.
#
# recheck: when nixpkgs bumps aw-server-rust past the commit that merged
# ActivityWatch/aw-server-rust#256 (currently only in unreleased 0.14.0
# betas) -- drop this patch, it will fail to apply (loud failure) once the
# upstream source already contains the fix.
_: _final: prev: {
  aw-server-rust = prev.aw-server-rust.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [
      ./aw-server-rust-no-panic-on-busy-commit.patch
    ];
    env = (old.env or { }) // {
      AW_WEBUI_DIR = prev.aw-server-rust.drvAttrs.AW_WEBUI_DIR.overrideAttrs (_webuiOld: {
        doCheck = false;
      });
    };
  });
}
