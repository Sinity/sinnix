{
  python3Packages,
  lib,
  makeWrapper,
  borgbackup,
  btrfs-progs,
  btrbk,
  coreutils,
  dolt,
  sqlite,
  systemd,
  util-linux,
  sinnix-borg-check,
  sinnix-borg-expire,
  sinnix-borg-prune-dumps,
  sinnix-sqlite-backup,
}:
python3Packages.buildPythonPackage {
  pname = "sinnix-backup";
  version = "0.1.0";
  pyproject = true;
  src = lib.fileset.toSource {
    root = ./.;
    fileset = lib.fileset.unions [
      ./pyproject.toml
      ./sinnix_backup
    ];
  };
  build-system = [ python3Packages.setuptools ];
  nativeBuildInputs = [ makeWrapper ];
  # The code calls every tool by bare name, so tests can put fakes first on PATH.
  postFixup = ''
    wrapProgram "$out/bin/sinnix-backup" --prefix PATH : ${
      lib.makeBinPath [
        borgbackup
        btrfs-progs
        btrbk
        coreutils
        dolt
        sqlite
        systemd
        util-linux
        sinnix-borg-check
        sinnix-borg-expire
        sinnix-borg-prune-dumps
        sinnix-sqlite-backup
      ]
    }
  '';
  doCheck = false;
  pythonImportsCheck = [
    "sinnix_backup.cli"
    "sinnix_backup.drain"
    "sinnix_backup.nightly"
    "sinnix_backup.coverage"
  ];
  meta.mainProgram = "sinnix-backup";
}
