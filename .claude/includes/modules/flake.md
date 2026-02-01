## Flake Organization

### `flake/` Directory

- **apps.nix**: Flake apps (switch, test, update, clean, check, etc.)
- **dev-shell.nix**: Development shell with pre-commit hooks
- **formatter.nix**: Nixpkgs-fmt configuration
- **nixos.nix**: NixOS configuration integration (imports modules/)
- **packages.nix**: Custom packages (shell scripts wrapped with dependencies)
- **tests.nix**: System tests
- **overlay/**: Nixpkgs overlays (package modifications, external integrations)
  - **package/**: Package overlays (individual files per package)
  - **patch/**: Patches for upstream packages

### Overlay vs Package: When to Use Each

**Use overlays** (`flake/overlay/package/*.nix`) when:
- Overriding existing nixpkgs packages (e.g., chromium with custom flags)
- Patching upstream packages (e.g., aw-server-rust with fix)
- Integrating external flake outputs into pkgs namespace

**Use packages** (`flake/packages.nix`) when:
- Creating custom shell scripts wrapped with dependencies
- Building standalone utilities specific to sinnix
- Adding new packages not in nixpkgs

**Example**:
```nix
# flake/packages.nix - custom scripts
packages.asbl-no-moar = pkgs.writeShellApplication {
  name = "asbl-no-moar";
  runtimeInputs = [ pkgs.bash pkgs.coreutils pkgs.procps ];
  text = ''exec ${pkgs.bash}/bin/bash ${inputs.self}/scripts/asbl-no-moar "$@"'';
};

# flake/overlay/package/chromium.nix - override existing package
final: prev: {
  chromium = prev.chromium.override {
    commandLineArgs = "--enable-features=TouchpadOverscrollHistoryNavigation";
  };
}
```
