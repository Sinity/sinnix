# Plannotator (https://github.com/backnotprop/plannotator, MIT or Apache-2.0)
# is a local, browser-based review surface for coding agents: plan review,
# document annotation, code review and an Inbox the agents write to.
#
# The upstream release binary is a self-contained compiled executable that
# carries its payload after the ELF image, so it is installed byte for byte
# (no strip, no patchelf) and runs through nix-ld. A new release is a version
# and hash bump here; the wrapper turns the binary's own update check off
# because it cannot replace a store path.
#
# The wrapper also keeps Plannotator out of files Home Manager owns. Left to
# itself it adds its Inbox server to each agent's configuration and writes a
# note into the agents' instruction files. Those integrations are declared in
# Sinnix instead: the hooks in dots/claude/managed-settings.json and
# modules/features/dev/agents/hooks.nix, the Inbox server in
# flake/data/mcp-registry.nix.
{
  lib,
  stdenvNoCC,
  fetchurl,
  makeWrapper,
}:
stdenvNoCC.mkDerivation (finalAttrs: {
  pname = "plannotator";
  version = "0.28.66";

  src = fetchurl {
    url = "https://github.com/backnotprop/plannotator/releases/download/v${finalAttrs.version}/plannotator-linux-x64.tar.xz";
    hash = "sha256-oJnfwZUORM/R4jKyN7MlkB8Ht/Qn8cRhZtiP1m1NTOg=";
  };
  sourceRoot = ".";

  nativeBuildInputs = [ makeWrapper ];

  dontConfigure = true;
  dontBuild = true;
  dontStrip = true;
  dontPatchELF = true;
  dontPatchShebangs = true;

  installPhase = ''
    runHook preInstall
    install -Dm755 plannotator-linux-x64 "$out/libexec/plannotator/plannotator"
    makeWrapper "$out/libexec/plannotator/plannotator" "$out/bin/plannotator" \
      --set PLANNOTATOR_UPDATE_CHECK 0 \
      --set PLANNOTATOR_AUTO_UPDATE 0 \
      --set PLANNOTATOR_INBOX_CONNECT 0 \
      --set PLANNOTATOR_INBOX_NOTES 0
    runHook postInstall
  '';

  meta = {
    description = "Browser-based plan, document and code review surface for coding agents";
    homepage = "https://github.com/backnotprop/plannotator";
    license = with lib.licenses; [
      mit
      asl20
    ];
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
    platforms = [ "x86_64-linux" ];
    mainProgram = "plannotator";
  };
})
