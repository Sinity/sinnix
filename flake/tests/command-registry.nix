# Verify the rendered rebuild entrypoints retain the environment contract gate.
{ inputs, ... }:
{
  perSystem =
    {
      pkgs,
      system,
      sinnixScriptRegistry,
      ...
    }:
    let
      commandRegistry = import ../command-registry.nix {
        inherit inputs pkgs system sinnixScriptRegistry;
      };
      rendered = pkgs.runCommand "command-registry-environment-gate" { } ''
        cat > "$out" <<'EOF'
        ${commandRegistry.appCommands.switch.script}
        --- test-system ---
        ${commandRegistry.appCommands.test-system.script}
        --- test-vm ---
        ${commandRegistry.appCommands.test-vm.script}
        EOF
        test "$(grep -c 'sinnixd-project-environment-check' "$out")" = 2
        if awk '/--- test-system ---/{section=1} /--- test-vm ---/{section=0} section && /sinnixd-project-environment-check/{gate=NR} section && /nh os test/{test=NR} END{exit !(gate && test && gate < test)}' "$out"; then :; else exit 1; fi
        if awk '/--- test-vm ---/{section=1} section && /sinnixd-project-environment-check/{bad=1} END{exit bad}' "$out"; then :; else exit 1; fi
      '';
    in
    {
      checks.command-registry-environment-gate = pkgs.runCommand "command-registry-environment-gate-check" { inherit rendered; } ''
        test -s "$rendered"
        touch "$out"
      '';
    };
}
