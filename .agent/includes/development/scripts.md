## Scripts Management

Scripts live in two places with distinct purposes:

1. **Source code**: `scripts/` directory (shell/Python scripts)
2. **Package definitions**: `flake/packages.nix` (wrappers with dependencies)

Each script requires:

- Source file in `scripts/`
- Package wrapper in `flake/packages.nix` with `runtimeInputs`
- Path reference via `${inputs.self}/scripts/name`

This pattern ensures scripts have proper PATH and dependencies without polluting the global environment.
