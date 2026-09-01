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
    in
    {
      checks.activitywatch-config = pkgs.runCommand "activitywatch-config-check" { }
        ''
          set -eu
          grep -Fq '"--config"' ${module}
          grep -Fq 'activitywatch/awatcher/awatcher.toml' ${module}
          grep -Fq 'idle-timeout-seconds = 60' ${module}
          grep -Fq 'Restart = "on-failure"' ${module}
          grep -Fq 'RestartSec = 5' ${module}
          grep -Fq 'ext-idle-notify' ${module}
          touch "$out"
        '';
      checks.activitywatch-awatcher-retry = pkgs.runCommand "activitywatch-awatcher-retry-check"
        { inherit awatcherPatched; }
        ''
          set -eu
          test -x "$awatcherPatched/bin/awatcher"
          test "$("$awatcherPatched/bin/awatcher" --version)" = "Activity Watcher 0.3.3"
          touch "$out"
        '';
    };
}
