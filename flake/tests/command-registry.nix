# Provably fails when an activating rebuild entrypoint loses or misorders the
# project-environment gate, or when the build-only VM route gains that gate.
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
        inherit
          inputs
          pkgs
          system
          sinnixScriptRegistry
          ;
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
        test "$(grep -c 'sinnixd-project-environment-check' "$out")" = 3
        for entrypoint in switch boot test-system; do
          command="nh os $entrypoint"
          test "$entrypoint" != test-system || command='nh os test'
          if awk -v start="--- $entrypoint ---" -v command="$command" '
            $0 == start { section = 1; next }
            /^--- / && section { section = 0 }
            section && /sinnixd-project-environment-check/ { gate = NR }
            section && index($0, command) { action = NR }
            END { exit !(gate && action && gate < action) }
          ' "$out"; then :; else exit 1; fi
        done
        if awk '/--- test-vm ---/{section=1} section && /sinnixd-project-environment-check/{bad=1} END{exit bad}' "$out"; then :; else exit 1; fi
      '';
    in
    {
      checks.command-registry-environment-gate =
        pkgs.runCommand "command-registry-environment-gate-check" { inherit rendered; }
          ''
            test -s "$rendered"
            touch "$out"
          '';
    };
}
