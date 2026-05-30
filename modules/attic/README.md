# Attic

Preserves Sinnix capabilities and services that are not in active use, while keeping their design and implementation available for revival or reference.

`mkAutoImports` excludes `attic/` (see `modules/default.nix`), so files here pay zero option-merge cost and are invisible to every host.

## Convention

### `cold/`

Preserved working modules that no host wants right now. Revival is `git mv` back to the original path under `modules/features/...` or `modules/services/...`. The module should compile without further changes — it was working when it left.

### `museum/`

Preserved design artifacts. The implementation may be stale, the wiring may have rotted, or the upstream tools it depended on may have changed. Revival is non-trivial; expect to update the module before it builds.

## Per-file headers

Every file in `attic/` carries a header at the top:

```
# attic/{cold,museum}: archived <date> [from <host>].
# Revive by `git mv` back to <original path>.
# Reason: <one line explaining what changed in the world>.
```

## Adding to the attic

When a capability is no longer in use:

1. `git mv` it from `modules/features/...` or `modules/services/...` into the matching `attic/{cold,museum}/` mirror path.
2. Prepend the header.
3. Remove any `sinnix.features.X.enable` or `sinnix.services.X.enable` lines from host configs that referenced it.
4. Commit the move + cleanup atomically.
