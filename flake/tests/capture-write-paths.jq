(.Service.Environment
  | map(select(startswith("SINNIX_CAPTURE_ROOT=")))
  | first
  | ltrimstr("SINNIX_CAPTURE_ROOT=")) as $root |
($captures[0] | map(select(.name == $lane)) | first) as $capture |
$root != null and
$capture != null and
($capture.path | startswith($root + "/")) and
(.Service.ReadWritePaths | any(
  . as $writable |
  ($writable | rtrimstr("/")) as $directory |
  ($writable | startswith("/")) and
  ($capture.path == $directory or ($capture.path | startswith($directory + "/")))
))
