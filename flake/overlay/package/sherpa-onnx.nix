# sherpa-onnx-vad-with-offline-asr, changed in two ways: silent input never
# constructs the recognizer, and one run takes many wave files, loading the
# model once (sinnix-stt hands it every window of a pass; one process per
# window re-read the 641 MB model about once a minute).
# recheck: when upstream defers the recognizer and accepts several inputs.
{ overlayLib, ... }:
overlayLib.mkPatchOverlay "sherpa-onnx" [
  ../patch/sherpa-onnx/vad-asr-batch.patch
]
