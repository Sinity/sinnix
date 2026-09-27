{
  lib,
  fetchurl,
  stdenvNoCC,
  unzip,
}:
stdenvNoCC.mkDerivation (finalAttrs: {
  pname = "tunnel-client";
  version = "0.0.15";

  src = fetchurl {
    url = "https://persistent.oaistatic.com/tunnel-client/v${finalAttrs.version}/tunnel-client-v${finalAttrs.version}-linux-amd64.zip";
    hash = "sha256-jINtxdaNaLZj2aXFso/5+ngNn3o//7HDBogLjzL6tfE=";
  };

  nativeBuildInputs = [ unzip ];
  sourceRoot = ".";
  dontBuild = true;

  installPhase = ''
    runHook preInstall
    install -Dm755 tunnel-client "$out/bin/tunnel-client"
    runHook postInstall
  '';

  meta = {
    description = "OpenAI Secure MCP Tunnel client";
    homepage = "https://github.com/openai/tunnel-client";
    license = lib.licenses.asl20;
    mainProgram = "tunnel-client";
    platforms = [ "x86_64-linux" ];
  };
})
