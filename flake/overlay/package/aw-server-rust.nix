{ inputs, ... }:
_final: prev: {
  # Override aw-server-rust with upstream master, which has the full PR #555
  # fix including the post-merge `merged_heartbeat.id = Some(event_id);`
  # seed 2026-05-26-aw-anomaly-audit.md for the source-level diff.
  aw-server-rust = prev.aw-server-rust.overrideAttrs (_old: {
    src = inputs.aw-server-rust;
    version = "0.13.2-upstream-master";
    cargoDeps = prev.rustPlatform.importCargoLock {
      lockFile = "${inputs.aw-server-rust}/Cargo.lock";
      allowBuiltinFetchGit = true;
    };
  });
}
