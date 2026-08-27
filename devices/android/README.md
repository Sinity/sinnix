# Android devices

`nix-android` records reviewed Android state and compares or applies it over an
explicit adb connection. Personal device snapshots and generated imports stay
under `/realm/data/self/devices/`, outside this public repository.

Inspect changes before applying them:

```console
nix run .#android-rebuild -- plan --flake .#redmi-note-11 --serial SERIAL
```

The Redmi profile uses `cleanup = "report"`: newly installed packages appear as
drift but are not removed. Change to `uninstall` only after the complete removal
plan has been reviewed.

The Nix-on-Droid app carries the declarative CLI environment:

```console
nix-on-droid switch --flake github:Sinity/sinnix#redmi-note-11
```

Plain Termux remains the SSH, boot, and Android-sensor host. Do not duplicate
its persistent services inside Nix-on-Droid.
