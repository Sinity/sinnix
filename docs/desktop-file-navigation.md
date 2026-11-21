# Desktop file navigation

GUI file navigation is Nautilus, with `ffmpegthumbnailer` and `evince` as
thumbnail helpers (video and PDF previews through XDG `.thumbnailer` entries),
the sidebar from `~/.config/gtk-3.0/bookmarks`, and the GTK portal file chooser
(`xdg-desktop-portal-gtk`), which reads the same bookmarks. Yazi is the
terminal route. Text files open in `sinnix-text-preview`; archives browse in
place through gvfs.

Where it is declared:

- `modules/features/desktop/common-apps.nix`: the manager, preview helpers and
  sidebar places (`sinnix.features.desktop.common-apps.fileNavigation`).
- `modules/features/desktop/ui.nix`: portal backends. FileChooser is named
  explicitly for `gtk`; the Hyprland portal does not implement it. Do not set
  `XDG_DESKTOP_PORTAL_DIR`: it makes the portal ignore its configuration.
- `modules/features/desktop/mime.nix`: handlers. `inode/directory` names
  Nautilus (undeclared, it resolved to kitty); `application/pdf` stays with
  qutebrowser even though evince installs a competing entry.

Nautilus was chosen over Thunar, Nemo and PCManFM-Qt after measuring previews,
sidebar and closure size: all covered the same previews, Thunar adds a second
thumbnail daemon, Nemo costs about ten times the closure, and PCManFM-Qt maps
its window with an empty Wayland app-id that Hyprland rules cannot target.

## Projected video previews

Yazi uses `media-preview-cache` for video previews. It projects spherical and
fisheye video into a centered, 90° horizontal view from one eye. Scrolling
changes the preview time. Ordinary video uses the existing thumbnailer.
Yazi requests thumbnails for the selected video. To precompute thumbnails
for a directory, run `media-preview-cache warm DIR`.

Use `video-projection inspect FILE` to see how a local file was identified.
If a video is missing projection or eye layout information, save the correction
with `video-projection set`. Other local players using this command share the
correction. The field of view describes the source image per eye.

```bash
video-projection set grid_LR_180.mp4 --projection equirect --layout sbs --hfov 180
video-projection clear grid_LR_180.mp4
```

In mpv, use Alt+arrow keys to look around, Alt+Page Up and Alt+Page Down
to zoom, and Alt+Home to recenter. Ctrl+Alt+O toggles the original video
and Ctrl+Alt+V opens projection and eye layout settings.

## Verification

```bash
nix build .#checks.x86_64-linux.desktop-file-navigation           # declared contract
nix build .#checks.x86_64-linux.desktop-file-navigation-previews  # helpers really thumbnail
nix build .#checks.x86_64-linux.desktop-file-navigation-places    # clean-profile bookmarks
nix build .#checks.x86_64-linux.desktop-file-navigation-mime      # declared handlers win
```

On the live session after a switch: `xdg-mime query default inode/directory`
answers `org.gnome.Nautilus.desktop`, and the portal journal
(`journalctl --user -u xdg-desktop-portal`) shows no "last-resort fallback"
for FileChooser.
