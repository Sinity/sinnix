# ActivityWatch watcher configuration and retry packaging checks.
{ inputs, ... }:
let
  module = ../../modules/features/desktop/activitywatch.nix;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      activitywatchOverlay = import ../overlay/package/activitywatch.nix { inherit inputs; } pkgs pkgs;
      awatcherPatched = activitywatchOverlay.awatcher;
      lib = inputs.nixpkgs.lib;
      testLib = import ../test-lib.nix { inherit inputs lib; };
      evaluated = testLib.evalTestSpec system (testLib.mkFeatureTest {
        name = "activitywatch-placement";
        feature = "sinnix.features.desktop.activitywatch.enable";
        assertions = _: [ ];
      });
      services = (testLib.hmFor evaluated.config).systemd.user.services;
      server = services.activitywatch.Service;
      watcher = services.activitywatch-watcher-awatcher.Service;
    in
    {
      checks.activitywatch-placement =
        assert builtins.all (
          service:
          service.Slice == "background.slice"
          && service.CPUWeight == 20
          && service.IOWeight == 20
          && service.Nice == 10
          && service.IOSchedulingPriority == 7
          && service.MemoryHigh == "1G"
        ) [ server watcher ];
        assert server.MemoryMax == "2G" && watcher.MemoryMax == "3G";
        assert watcher.Restart == "on-failure" && watcher.RestartSec == 5;
        pkgs.runCommand "activitywatch-placement-check" { } ''touch "$out"'';
      checks.activitywatch-config = pkgs.runCommand "activitywatch-config-check" { } ''
        set -eu
        grep -Fq '"--config"' ${module}
        grep -Fq 'activitywatch/awatcher/awatcher.toml' ${module}
        grep -Fq 'idle-timeout-seconds = 60' ${module}
        grep -Fq 'Restart = "on-failure"' ${module}
        grep -Fq 'RestartSec = 5' ${module}
        grep -Fq 'ext-idle-notify' ${module}
        touch "$out"
      '';
      checks.activitywatch-awatcher-retry =
        pkgs.runCommand "activitywatch-awatcher-retry-check" { inherit awatcherPatched; }
          ''
            set -eu
            test -x "$awatcherPatched/bin/awatcher"
            test "$("$awatcherPatched/bin/awatcher" --version)" = "Activity Watcher ${awatcherPatched.version}"
            touch "$out"
          '';
    };
}
