# Xiaomi cloud capture (sinnix-ogll).
#
# The protocol client is upstream GPL-3 TypeScript (miband-bot), pinned and
# fetched here rather than vendored into this repository -- the checkout
# stays byte-auditable against upstream, and this public repo carries only
# the thin orchestration entry (xiaomi-sync.ts). Bun runs the TypeScript
# directly; the client needs nothing beyond node builtins, so there is no
# lockfile, no node_modules, and no build step.
{
  lib,
  stdenvNoCC,
  fetchFromGitHub,
  bun,
  makeWrapper,
  python3,
}:

stdenvNoCC.mkDerivation {
  pname = "sinnix-capture-xiaomi-cloud";
  version = "0.1.0";

  src = ./.;

  upstream = fetchFromGitHub {
    owner = "alexgetmancom";
    repo = "miband-bot";
    rev = "99a22e11bd045b18375f89e3439c120b747573bc";
    hash = "sha256-Ao+vO2h2//lXze3GpP5hafuE8q0zZreir1b71qhPfgc=";
  };

  nativeBuildInputs = [ makeWrapper ];
  nativeCheckInputs = [
    bun
    python3
  ];
  doCheck = true;
  checkPhase = ''
    runHook preCheck
    BUN=${lib.getExe bun} ${lib.getExe python3} test_cli.py
    BUN=${lib.getExe bun} ${lib.getExe python3} test_sync.py
    runHook postCheck
  '';

  installPhase = ''
    runHook preInstall
    mkdir -p $out/share/sinnix-capture-xiaomi-cloud $out/bin
    cp xiaomi-sync.ts xiaomi-login.ts $out/share/sinnix-capture-xiaomi-cloud/
    cp -r $upstream $out/share/sinnix-capture-xiaomi-cloud/upstream
    chmod -R u+w $out/share/sinnix-capture-xiaomi-cloud/upstream
    substituteInPlace $out/share/sinnix-capture-xiaomi-cloud/upstream/src/xiaomi/client.ts \
      --replace-fail \
        'const XIAOMI_REQUEST_TIMEOUT_MS = 30_000;' \
        'const XIAOMI_REQUEST_TIMEOUT_MS = 120_000;'
    makeWrapper ${lib.getExe bun} $out/bin/sinnix-capture-xiaomi-cloud \
      --add-flags "run $out/share/sinnix-capture-xiaomi-cloud/xiaomi-sync.ts"
    makeWrapper ${lib.getExe bun} $out/bin/sinnix-xiaomi-cloud-login \
      --add-flags "run $out/share/sinnix-capture-xiaomi-cloud/xiaomi-login.ts"
    runHook postInstall
  '';

  meta = {
    description = "Xiaomi cloud health capture: band data fetched from Xiaomi's servers into the lake (second witness beside Health Connect)";
    mainProgram = "sinnix-capture-xiaomi-cloud";
    # Combined work with the GPL-3 upstream client at runtime.
    license = lib.licenses.gpl3Plus;
  };
}
