{ pkgs, entry }:
let
  # Integrity walks must be able to map the whole immutable database.
  sqlite = pkgs.sqlite.overrideAttrs (old: {
    env = (old.env or { }) // {
      NIX_CFLAGS_COMPILE = (old.env.NIX_CFLAGS_COMPILE or "") + " -DSQLITE_MAX_MMAP_SIZE=1099511627776";
    };
  });
  libraryPath = pkgs.lib.makeLibraryPath [ sqlite ];
  mmapCheck = pkgs.runCommand "sqlite-backup-mmap-check" { } ''
    LD_LIBRARY_PATH=${libraryPath} ${pkgs.python3}/bin/python - <<'PY'
    import sqlite3
    with sqlite3.connect("fixture.sqlite") as connection:
        connection.execute("CREATE TABLE sample (value INTEGER)")
        requested = 64 * 1024**3
        actual = connection.execute(f"PRAGMA mmap_size={requested}").fetchone()[0]
        assert actual == requested, (actual, requested)
    PY
    touch "$out"
  '';
in
entry
// {
  package = pkgs.writeShellApplication {
    name = "sinnix-sqlite-backup";
    text = ''
      test -e ${mmapCheck}
      export LD_LIBRARY_PATH=${libraryPath}
      exec ${entry.package}/bin/sinnix-sqlite-backup "$@"
    '';
    meta.description = entry.description;
  };
}
