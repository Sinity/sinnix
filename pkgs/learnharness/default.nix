# LearnHarness (https://github.com/amosblomqvist/learnharness, AGPL-3.0) is a
# desktop tutor. It runs lessons through an installed Claude Code CLI or a
# ChatGPT sign-in, so it needs no API key. The upstream AppImage is pinned:
# its in-app updater cannot replace a store path, so a new release is a
# version and hash bump here.
{
  lib,
  appimageTools,
  fetchurl,
  # The app offers only the Claude Code aliases opus, sonnet and haiku. This is
  # the model its "opus" choice resolves to; null leaves the CLI default.
  claudeOpusModel ? "claude-opus-5-5",
}:
let
  pname = "learnharness";
  version = "0.6.1";
  src = fetchurl {
    url = "https://github.com/amosblomqvist/learnharness/releases/download/v${version}/LearnHarness-${version}-x86_64.AppImage";
    hash = "sha256-uKAz63QhZ3iT2W5JiLMBU/3+T8bw3EVveUcWG7oEG5g=";
  };
  contents = appimageTools.extract { inherit pname version src; };
in
appimageTools.wrapType2 {
  inherit pname version src;

  profile = lib.optionalString (claudeOpusModel != null) ''
    export ANTHROPIC_DEFAULT_OPUS_MODEL="''${ANTHROPIC_DEFAULT_OPUS_MODEL:-${claudeOpusModel}}"
  '';

  extraInstallCommands = ''
    install -Dm444 ${contents}/learnharness.desktop "$out/share/applications/learnharness.desktop"
    substituteInPlace "$out/share/applications/learnharness.desktop" \
      --replace-fail "Exec=AppRun --no-sandbox" "Exec=learnharness"
    cp -r ${contents}/usr/share/icons "$out/share/icons"
  '';

  meta = {
    description = "Agent harness for learning: adaptive teaching, practice and a knowledge graph";
    homepage = "https://github.com/amosblomqvist/learnharness";
    license = lib.licenses.agpl3Only;
    platforms = [ "x86_64-linux" ];
    mainProgram = "learnharness";
  };
}
