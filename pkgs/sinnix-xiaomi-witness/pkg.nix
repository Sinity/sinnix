# Xiaomi cloud vendor witness (sinnix-ogll).
#
# The protocol client is upstream GPL-3 TypeScript (miband-bot), pinned and
# fetched here rather than vendored into this repository -- the checkout
# stays byte-auditable against upstream, and this public repo carries only
# the thin orchestration entry (witness-sync.ts). Bun runs the TypeScript
# directly; the client needs nothing beyond node builtins, so there is no
# lockfile, no node_modules, and no build step.
{
  lib,
  stdenvNoCC,
  fetchFromGitHub,
  bun,
  makeWrapper,
}:

stdenvNoCC.mkDerivation {
  pname = "sinnix-xiaomi-witness";
  version = "0.1.0";

  src = ./.;

  upstream = fetchFromGitHub {
    owner = "alexgetmancom";
    repo = "miband-bot";
    rev = "99a22e11bd045b18375f89e3439c120b747573bc";
    hash = "sha256-Ao+vO2h2//lXze3GpP5hafuE8q0zZreir1b71qhPfgc=";
  };

  nativeBuildInputs = [ makeWrapper ];

  installPhase = ''
    runHook preInstall
    mkdir -p $out/share/sinnix-xiaomi-witness $out/bin
    cp witness-sync.ts witness-login.ts $out/share/sinnix-xiaomi-witness/
    cp -r $upstream $out/share/sinnix-xiaomi-witness/upstream
    makeWrapper ${lib.getExe bun} $out/bin/sinnix-xiaomi-witness \
      --add-flags "run $out/share/sinnix-xiaomi-witness/witness-sync.ts"
    makeWrapper ${lib.getExe bun} $out/bin/sinnix-xiaomi-witness-login \
      --add-flags "run $out/share/sinnix-xiaomi-witness/witness-login.ts"
    runHook postInstall
  '';

  meta = {
    description = "Xiaomi cloud health witness: band data fetched from Xiaomi's servers into the lake (second witness beside Health Connect)";
    mainProgram = "sinnix-xiaomi-witness";
    # Combined work with the GPL-3 upstream client at runtime.
    license = lib.licenses.gpl3Plus;
  };
}
