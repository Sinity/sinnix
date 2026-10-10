{
  pkgs,
  src,
  name,
}:
let
  locks = builtins.fromJSON (builtins.readFile ../../flake/data/agent-platform-locks.json);
  lock = locks.${name};
  native = lock.packages.${"node_modules/${name}-linux-x64"};
  nativeArchive = pkgs.fetchurl {
    url = native.resolved;
    hash = native.integrity;
  };
  lockFile = pkgs.writeText "platform-recovery-lock.json" (builtins.toJSON lock);
  safeName = pkgs.lib.replaceStrings [ "@" "/" ] [ "" "-" ] name;
in
pkgs.runCommand "${safeName}-${lock.version}-integrity-locked.tgz"
  {
    nativeBuildInputs = [ pkgs.python3 ];
    passthru.original = src;
  }
  ''
    python3 ${./lock-platform.py} ${src} ${lockFile} ${nativeArchive} "$out"
  ''
