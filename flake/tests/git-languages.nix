# Dev feature runtime checks: git/delta tooling and language toolchains.
#
# dev-git-runtime is promoted into the default `checks` tier (sinnix-7bu): it
# evaluates the small dev.git feature module (git + delta only) and asserts a
# handful of `git config --get` values plus `delta --version` — cheap
# relative to dev-languages-runtime, which pulls a much larger closure
# (python3.withPackages, nodejs, sqlite, gh) via the full HM home path and
# stays in heavyChecks.
#
# Split out of the former flake/tests-runtime.nix monolith (sinnix-7bu).
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      testLib = import ../test-lib.nix { inherit inputs lib; };
      inherit (testLib)
        mkFeatureTest
        mkHmRuntimeCheck
        ;

      devGitRuntimeSpec = mkFeatureTest {
        name = "dev-git-runtime";
        feature = "sinnix.features.dev.git.enable";
        assertions = _config: [ ];
      };
      devLanguagesRuntimeSpec = mkFeatureTest {
        name = "dev-languages-runtime";
        feature = "sinnix.features.dev.languages.enable";
        assertions = _config: [ ];
      };

      devGitRuntime = mkHmRuntimeCheck system {
        name = "dev-git-runtime-check";
        spec = devGitRuntimeSpec;
        nativeBuildInputs = [
          pkgs.delta
          pkgs.git
          pkgs.gnugrep
        ];
        homeFiles = [ ".config/git/ignore_global" ];
        xdgConfigFiles = [ "git/config" ];
        script = ''
          git config --global --get init.defaultBranch | grep -qx 'master'
          git config --global --get merge.conflictStyle | grep -qx 'zdiff3'
          git config --global --get pull.rebase | grep -qx 'true'
          git config --global --get rerere.enabled | grep -qx 'true'
          git config --global --get credential.https://github.com.helper | grep -q '/run/agenix/github-token'
          grep -q '^AGENTS.md$' "$HOME/.config/git/ignore_global"
          delta --version >/dev/null
        '';
      };
      devLanguagesRuntime = mkHmRuntimeCheck system {
        name = "dev-languages-runtime-check";
        spec = devLanguagesRuntimeSpec;
        nativeBuildInputs = [
          pkgs.coreutils
          pkgs.gnugrep
        ];
        script = ''
          python --version >/dev/null
          node --version >/dev/null
          sqlite3 --version >/dev/null
          gh --version >/dev/null
        '';
      };
    in
    {
      checks = {
        dev-git-runtime = devGitRuntime;
      };

      heavyChecks = {
        dev-languages-runtime = devLanguagesRuntime;
      };
    };
}
