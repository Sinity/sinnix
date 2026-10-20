{
  python3Packages,
  lib,
  makeWrapper,
  sinnix-lib,
  duckdb,
  coreutils,
  file,
  util-linux,
  btrfs-progs,
  ripgrep,
  uv,
  compsize,
  nix,
}:
python3Packages.buildPythonPackage {
  pname = "sinnix-fs";
  version = "0.1.0";
  pyproject = true;
  src = lib.fileset.toSource {
    root = ./.;
    fileset = lib.fileset.unions [
      ./pyproject.toml
      ./sinnix_fs
    ];
  };
  build-system = [ python3Packages.setuptools ];
  dependencies = [ sinnix-lib ];
  nativeBuildInputs = [ makeWrapper ];
  postFixup = ''
    wrapProgram "$out/bin/sinnix-fs" --prefix PATH : ${
      lib.makeBinPath [
        duckdb
        coreutils
        file
        util-linux
        btrfs-progs
        ripgrep
        uv
        compsize
        nix
      ]
    }
  '';
  doCheck = false;
  pythonImportsCheck = [
    "sinnix_fs.cli"
    "sinnix_fs.inventory"
    "sinnix_fs.catalog"
    "sinnix_fs.layout"
  ];
  meta.mainProgram = "sinnix-fs";
}
