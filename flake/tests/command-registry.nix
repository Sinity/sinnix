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
        --- switch ---
        ${commandRegistry.appCommands.switch.script}
        --- boot ---
        ${commandRegistry.appCommands.boot.script}
        --- test-system ---
        ${commandRegistry.appCommands.test-system.script}
        --- test-vm ---
        ${commandRegistry.appCommands.test-vm.script}
        EOF
        # Provably fails when a covered command loses its gate or the gate is
        # moved after the command invocation.
        test "$(grep -c 'sinnixd-project-environment-check' "$out")" = 3
        if awk '/--- switch ---/{section=1} /--- boot ---/{section=0} section && /sinnixd-project-environment-check/{gate=NR} section && /nh os switch/{switch_line=NR} END{exit !(gate && switch_line && gate < switch_line)}' "$out"; then :; else exit 1; fi
        if awk '/--- boot ---/{section=1} /--- test-system ---/{section=0} section && /sinnixd-project-environment-check/{gate=NR} section && /nh os boot/{boot=NR} END{exit !(gate && boot && gate < boot)}' "$out"; then :; else exit 1; fi
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
