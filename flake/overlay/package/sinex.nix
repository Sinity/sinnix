{ inputs, ... }:
# Apply sinex flake overlay — injects pg_jsonschema into postgresql18Packages
# Required by services.sinex database module (database.nix hard-throws without it)
inputs.sinex.overlays.default
