# Dev feature runtime checks: git/delta tooling and language toolchains.
#
# dev-git-runtime sits in the default `checks` tier: it evaluates the small
# dev.git feature module (git + delta only) and asserts a handful of
# `git config --get` values plus `delta --version` — cheap relative to
# dev-languages-runtime, which pulls a much larger closure
# (python3.withPackages, nodejs, sqlite, gh) via the full HM home path.
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

      # Provably fails when: the agenix github-token path stops reaching the
      # rendered credential helper, the shared ignore_global dots file stops
      # being deployed, or delta drops out of the feature's package set.
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
