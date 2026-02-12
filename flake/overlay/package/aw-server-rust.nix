{ inputs, ... }:
final: prev: {
  # Override aw-server-rust with the heartbeat fix from PR #555
  # Fixes SQL query mismatch causing duplicate events and failed heartbeat merges
  aw-server-rust = prev.aw-server-rust.overrideAttrs (old: {
    src = inputs.aw-server-rust;
    version = "0.13.2-heartbeat-fix";
    # The Cargo.lock hasn't changed, only the source, so we can reuse the existing cargoHash
    # But we need to point cargoDeps at the new source
    cargoDeps = prev.rustPlatform.importCargoLock {
      lockFile = "${inputs.aw-server-rust}/Cargo.lock";
      # Allow git dependencies (aw-server-rust has some)
      allowBuiltinFetchGit = true;
    };
  });
}
