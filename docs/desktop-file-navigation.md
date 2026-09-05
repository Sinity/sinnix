# Desktop file navigation

GUI file navigation on sinnix-prime is one manager (Nautilus), one preview
mechanism (XDG `.thumbnailer` entries), one sidebar (`gtk-3.0/bookmarks`), and
one portal file chooser (`xdg-desktop-portal-gtk`). Yazi remains the terminal
route and is unchanged.

Ownership: `modules/features/desktop/common-apps.nix` declares the manager, its
preview helpers and the sidebar places under
`sinnix.features.desktop.common-apps.fileNavigation`;
`modules/features/desktop/ui.nix` declares the portal backends;
`modules/features/desktop/mime.nix` declares the content-type handlers,
including `inode/directory`.

## Measurement

Every candidate was opened on the live Hyprland 0.56.1 session against one
fixture directory (`png`, `jpg`, `mp4`, `pdf`, `txt`, `md`, `zip`, `tar.gz`)
with a clean `HOME` whose only configuration was the seven-line bookmarks file.
The window was confirmed in `hyprctl clients -j` and closed with `hyprctl
dispatch closewindow`. Previews were counted from the candidate's own
`$XDG_CACHE_HOME/thumbnails` tree, keyed by the MD5 of each file URI, so a
"yes" means the manager wrote a thumbnail of that file, not that a feature list
claims support. Cost is the closure a candidate adds to the live user profile,
not its total closure.

| Candidate                                    | Previews          | Sidebar places | Wayland app-id       | Added to the profile      |
| -------------------------------------------- | ----------------- | -------------- | -------------------- | ------------------------- |
| Nautilus 50.2.2, as configured before        | image only        | 7 of 7         | `org.gnome.Nautilus` | —                         |
| Nautilus 50.2.2 + ffmpegthumbnailer + evince | image, video, PDF | 7 of 7         | `org.gnome.Nautilus` | 28.5 MiB, 10 store paths  |
| Thunar 4.20.9 + tumbler 4.20.2               | image, video, PDF | 7 of 7         | `thunar`             | 31.1 MiB, 17 store paths  |
| Nemo 6.6.4 + the same two helpers            | image, video, PDF | 7 of 7         | `nemo`               | 280.8 MiB, 73 store paths |
| PCManFM-Qt 2.4.0 + tumbler + the helpers     | image, video, PDF | 7 of 7         | _empty_              | 8.5 MiB, 8 store paths    |

Facts behind the table:

- The host installed no thumbnailers at all, so the incumbent could only
  preview what gdk-pixbuf decodes. That is the whole of the incumbent's
  measured deficiency.
- `ffmpegthumbnailer` was already in the profile's closure through
  `scripts/media-preview-cache`, but its `.thumbnailer` entry was not on
  `XDG_DATA_DIRS`. Installing it registers video previews for no new bytes.
- No candidate thumbnails text or archives. Text opening already belongs to
  `sinnix-text-preview` (a bat popup, `mime.nix`), and archives browse in place
  through the gvfs archive backend: mounting the fixture zip, listing it and
  reading a nested member through `/run/user/1000/gvfs` all worked against the
  running `gvfs-daemon`.
- Every candidate read the same `~/.config/gtk-3.0/bookmarks` file, labels
  included, and every place was one click away. The sidebar is therefore not a
  manager-specific surface.

## Portal file selection

The portal backend is independent of the manager: of the two installed
backends, only `gtk.portal` declares
`org.freedesktop.impl.portal.FileChooser`; `hyprland.portal` declares only
Screenshot, ScreenCast, GlobalShortcuts and InputCapture. One live `OpenFile`
request over D-Bus mapped a native Wayland dialog owned by
`xdg-desktop-portal-gtk`, and the GTK chooser reads the same bookmarks file as
the manager sidebar.

That selection was, however, a fallback rather than a decision:
`xdg.portal.config` was inert because the portal user unit set
`XDG_DESKTOP_PORTAL_DIR`. xdg-desktop-portal treats that variable as a test
hook — when it is set, one directory replaces the entire configuration _and_
backend search, and `/etc/xdg/xdg-desktop-portal/hyprland-portals.conf` is
never read. The running instance logged `Choosing gtk.portal for
org.freedesktop.impl.portal.FileChooser as a last-resort fallback` for every
interface the deprecated `UseIn` key did not claim. The systemd user manager
already exports `XDG_DATA_DIRS` and `XDG_CONFIG_DIRS`, so the override bought
nothing; it is removed, and FileChooser is now named explicitly in both the
common and Hyprland sections.

## Choice

Nautilus, with `ffmpegthumbnailer` and `evince` as preview helpers.

It matches every alternative's measured preview coverage, keeps the current
manager, adds no daemon, and costs the least of the candidates that satisfy the
compositor's window-rule contract. The remaining differences between the
candidates were not in the criteria.

Rejected:

- **Thunar + tumbler** — equal coverage, no measured advantage, and it replaces
  fork-per-file `.thumbnailer` execution with a D-Bus-activated thumbnail
  daemon. That is a second preview mechanism to own for the same result.
- **Nemo** — equal coverage at roughly nine times the incremental closure
  (280.8 MiB, 73 store paths), pulling cinnamon-desktop,
  cinnamon-translations, dconf-editor and MATE libraries behind a file manager.
- **PCManFM-Qt** — the cheapest closure and full coverage through tumbler, but
  it maps its window with an empty `app_id` under Hyprland 0.56.1 (checked
  again after the window settled). No window, group or float rule can address
  it, which disqualifies it on a compositor whose workflow is keyed on app-id.

## Handlers

`inode/directory` now names the manager. Undeclared, it resolved by
desktop-entry order to `kitty-open.desktop`, so opening a folder from any
application launched a terminal. The terminal route stays deliberate: Yazi is
started as a program, not reached through a MIME dispatch.

`evince` ships a document-viewer desktop entry, which is exactly the kind of
package that silently takes over a type. `application/pdf` remains declared to
qutebrowser, and `flake/tests/desktop-file-navigation.nix` resolves both types
through GIO against an environment containing the competing entries.

## Verification

```bash
nix build .#checks.x86_64-linux.desktop-file-navigation           # declared contract
nix build .#checks.x86_64-linux.desktop-file-navigation-previews  # helpers really thumbnail
nix build .#checks.x86_64-linux.desktop-file-navigation-places    # clean-profile bookmarks
nix build .#checks.x86_64-linux.desktop-file-navigation-mime      # declared handlers win
```

After a switch, on the live session:

```bash
systemctl --user restart xdg-desktop-portal
journalctl --user -u xdg-desktop-portal --since -1min | grep FileChooser
xdg-mime query default inode/directory
busctl --user call org.freedesktop.portal.Desktop /org/freedesktop/portal/desktop \
  org.freedesktop.portal.FileChooser OpenFile ssa{sv} "" "portal probe" 0
```

The journal must no longer report a last-resort fallback for FileChooser,
`xdg-mime` must answer `org.gnome.Nautilus.desktop`, and the probe must map a
dialog whose `class` in `hyprctl clients -j` is `xdg-desktop-portal-gtk`.
