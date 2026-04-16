## Troubleshooting

### Module Not Found

```
error: attribute 'X' missing
```

**Fix**: Check imports in `modules/{category}/default.nix`, ensure file is listed.

### Circular Dependency

```
error: infinite recursion encountered
```

**Fix**: Check for modules referencing each other. Use `lib.mkIf` to break cycles.

### Build Fails After Moving Module

```
error: option 'sinnix.old.path.enable' used but not defined
```

**Fix**: Search for old option path in host configs and bundles, update references.
