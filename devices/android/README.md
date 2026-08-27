# Android devices

`nix-android` records reviewed Android state and compares or applies it over an
explicit adb connection. Personal device snapshots and generated imports stay
under `/realm/data/self/devices/`, outside this public repository.

Inspect changes before applying them:

```console
nix run .#android-rebuild -- plan --flake .#redmi-note-11 --serial SERIAL
```

Do not enable app cleanup until every retained app is declared and the removal
plan has been reviewed.
