{
  pkgs,
  src,
  name,
}:
let
  locks = builtins.fromJSON (builtins.readFile ../../flake/data/agent-cli-locks.json);
  lock = locks.${name};
  nativeArchive =
    if
      builtins.elem name [
        "@anthropic-ai/claude-code"
        "@openai/codex"
      ]
    then
      let
        native = lock.packages.${"node_modules/${name}-linux-x64"};
      in
      pkgs.fetchurl {
        url = native.resolved;
        hash = native.integrity;
      }
    else
      "-";
  lockFile = pkgs.writeText "dependency-recovery-lock.json" (builtins.toJSON lock);
  safeName = pkgs.lib.replaceStrings [ "@" "/" ] [ "" "-" ] name;
in
pkgs.runCommand "${safeName}-${lock.version}-integrity-locked.tgz"
  {
    nativeBuildInputs = [ pkgs.python3 ];
    passthru.original = src;
  }
  ''
    python3 ${./lock-source.py} ${src} ${lockFile} ${nativeArchive} "$out"
  ''
