# Silent VAD windows need no recognizer model or inference sessions.
# recheck: when upstream constructs OfflineRecognizer only after VAD emits speech.
{ overlayLib, ... }:
overlayLib.mkPatchOverlay "sherpa-onnx" [
  ../patch/sherpa-onnx/defer-asr-until-speech.patch
]
