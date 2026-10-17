# Use the owner's recipe in the shared package set, retaining the existing
# caption-package metadata and OpenAI test-input pruning.
{ inputs, ... }:
final: _prev:
let
  openai = final.python312Packages.openai.overrideAttrs (old: {
    # buildPythonPackage materializes nativeCheckInputs as
    # nativeInstallCheckInputs in the final derivation. Clearing
    # nativeCheckInputs alone is too late for overrideAttrs.
    nativeInstallCheckInputs = [ ];
    doCheck = false;
  });
  replaceOpenai = input: if final.lib.getName input == "openai" then openai else input;
  ytPolisher =
    (inputs.yt-polisher.overlays.default final _prev).yt-polisher.overridePythonAttrs
      (old: {
        # The input's Nix package covers captions; its uv environment owns local
        # model backends. Keep the wheel metadata consistent with that package.
        pythonRemoveDeps = [
          "chatterbox-tts"
          "datasets"
          "demucs"
          "f5-tts"
          "faster-whisper"
          "mediapipe"
          "pyannote-audio"
          "resemblyzer"
          "torch"
          "torchaudio"
        ];
        dependencies = map replaceOpenai (old.dependencies or [ ]) ++ [
          final.python312Packages.huggingface-hub
          final.python312Packages.num2words
        ];
        pythonImportsCheck = (old.pythonImportsCheck or [ ]) ++ [ "yt_polisher.__main__" ];
      });
in
{
  yt-polisher = ytPolisher;
}
