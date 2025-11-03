## Zed key bindings on NixOS

- **Package** – Zed ships as the `zed-editor` package in `nixpkgs` (unfree). Add it through Home Manager (e.g. `home.packages = [ pkgs.zed-editor ];`) or use `nix profile install nixpkgs#zed-editor` for a throwaway test.
- **Binary cache** – the build is wrapped in `nixpkgs`, so no extra cache configuration is required beyond your existing substituters.
- **Config path** – key bindings live in `~/.config/Zed/keymap.json`. Home Manager can manage this file with `xdg.configFile."Zed/keymap.json".source = ./path/to/keymap.json;`.
- **Format** – the doc at <https://zed.dev/docs/key-bindings> lists the command IDs. Bindings are a JSON array; each entry accepts `"commands"` and `"keymaps"`.
- **Restart** – Zed reloads the keymap on save, but restart the editor if the file contains syntax errors so it falls back to defaults.
- **Version control** – check the managed file into `dots/zed/keymap.json` so it can be shared and versioned like the rest of your tooling configs.
