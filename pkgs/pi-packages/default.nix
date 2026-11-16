# Third-party pi packages, pinned and installed without pi's package manager.
#
# `pi install` would clone or `npm install` each package into ~/.pi at run
# time, with floating transitive dependencies, and extensions run inside the
# pi process with access to its credentials. Here every package is a store
# path: the three npm packages come from one lock file beside this file
# (package.json holds the exact versions), the two Git sources are fixed
# revisions, and pi loads all of them as local paths
# (modules/features/dev/agents/pi.nix).
#
# To bump an npm package: edit the version in package.json, run
# `npm install --package-lock-only --legacy-peer-deps --ignore-scripts` here,
# and replace npmDepsHash with the one the failed build prints.
# `--legacy-peer-deps` keeps pi's own packages, which every extension names
# as a peer, out of the lock: pi supplies them, and a second copy breaks its
# module mapping.
{
  lib,
  buildNpmPackage,
  fetchFromGitHub,
  python3,
}:
let
  # Claude models on a Claude plan: each turn runs through the installed
  # Claude Code CLI (`claude -p`), which holds the sign-in. No dependencies.
  claudeCode = fetchFromGitHub {
    owner = "earendil-works";
    repo = "pi-claude-code";
    rev = "d5b5e04c314d3452d357174d16d10dda34daa2d2";
    hash = "sha256-86zfGr9YoM+I/PmWHDJb8AbcxhYC1m8aOeghJjvN414=";
  };
  # Only extensions/answer.ts is loaded from this repository: `/answer`
  # collects the questions in the last reply into one form.
  agentStuff = fetchFromGitHub {
    owner = "mitsuhiko";
    repo = "agent-stuff";
    rev = "0865c849befd2021490679f96a8dee58c84ac857";
    hash = "sha256-tIKtwPCXCYhYza7BgRQiRK+Lv9YrI+xpDtfSPrzR3w4=";
  };
in
buildNpmPackage {
  pname = "pi-packages";
  version = "1.0.0";
  src = lib.fileset.toSource {
    root = ./.;
    fileset = lib.fileset.unions [
      ./package.json
      ./package-lock.json
    ];
  };
  npmDepsHash = "sha256-H5huTIH98s7MCVf/zhYbLYJmEmb3WRLtmqfkc5R8S+o=";
  npmFlags = [ "--legacy-peer-deps" ];
  # node-pty (Plannotator's browser terminal) compiles with node-gyp.
  nativeBuildInputs = [ python3 ];
  dontNpmBuild = true;
  dontNpmPrune = true;

  installPhase = ''
    runHook preInstall
    mkdir -p "$out"
    cp -r node_modules "$out/node_modules"
    ln -s ${claudeCode} "$out/pi-claude-code"
    install -Dm644 ${agentStuff}/extensions/answer.ts "$out/answer/answer.ts"
    runHook postInstall
  '';

  passthru = {
    # What pi's `packages` setting lists, in load order.
    packagePaths = [
      "node_modules/@plannotator/pi-extension"
      "node_modules/pi-web-access"
      "node_modules/pi-subagents"
      "pi-claude-code"
      "answer/answer.ts"
    ];
  };

  meta = {
    description = "Pinned third-party pi packages: Plannotator, web access, subagents, Claude Code provider, /answer";
    platforms = lib.platforms.linux;
  };
}
