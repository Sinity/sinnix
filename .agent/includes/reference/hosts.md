## Host Configuration

Host-specific configs in `hosts/{hostname}/`:

- **sinnix-prime**: Desktop workstation (Intel i7-13700K, RTX 4080)
- **sinnix-ethereal**: Secondary machine

Each host:

1. Imports shared modules via `../modules`
2. Sets machine-specific options (boot, storage, display, input)
3. Enables services and opts out of default-on features selectively

Example:

```nix
# hosts/sinnix-prime/default.nix
{
  imports = [
    ../../modules
    ./boot.nix
    ./display.nix
    ./storage.nix
    ./input.nix
  ];

  sinnix = {
    services.sinex.enable = true;
    services.polylogue.enable = true;
    features.desktop.gaming.enable = false;
  };
}
```
