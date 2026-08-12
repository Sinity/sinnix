# Dev feature runtime checks: git/delta tooling and language toolchains.
#
# dev-git-runtime is promoted into the default `checks` tier (sinnix-7bu): it
# evaluates the small dev.git feature module (git + delta only) and asserts a
# handful of `git config --get` values plus `delta --version` — cheap
# relative to dev-languages-runtime, which pulls a much larger closure
# (python3.withPackages, nodejs, sqlite, gh) via the full HM home path and
# used to live in the heavyChecks quarantine tier (promoted 2026-08-12:
# measured ~22s, and the tier never ran anywhere, letting red checks hide).
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
          # Cross-module wiring: the agenix secret path must actually reach
          # the rendered git config, not just a literal restatement of a
          # config value the module itself set.
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

      checks = {
        dev-languages-runtime = devLanguagesRuntime;
      };
    };
}
