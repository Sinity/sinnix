# Dev feature runtime checks: git/delta tooling and language toolchains.
#
# dev-git-runtime sits in the default `checks` tier: it evaluates the small
# dev.git feature module (git, delta, and the gh binary the credential helper
# names) and asserts rendered `git config` wiring plus `delta --version` —
# cheap relative to dev-languages-runtime, which pulls a much larger closure
# (python3.withPackages, nodejs, sqlite) via the full HM home path.
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

      # Provably fails when: the gh store path stops reaching the rendered
      # credential helper, the helper stops ending the exchange without a
      # login, the shared ignore_global dots file stops being deployed, or
      # delta drops out of the feature's package set.
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
          pkgs.gh
          pkgs.git
          pkgs.gnugrep
        ];
        homeFiles = [ ".config/git/ignore_global" ];
        xdgConfigFiles = [ "git/config" ];
        script = ''
          # Cross-module wiring: the GitHub credential helper must reach gh
          # through an absolute store path, not the ambient PATH.
          helper="$(git config --global --get credential.https://github.com.helper)"
          case "$helper" in
            *"/nix/store/"*"/bin/gh auth git-credential"*) ;;
            *)
              echo "credential helper does not reach gh by store path: $helper" >&2
              exit 1
              ;;
          esac

          # With no gh login available the helper must end the credential
          # exchange. Answering nothing instead lets git fall through to an
          # interactive terminal prompt, which blocks an unattended push.
          if printf 'protocol=https\nhost=github.com\n\n' \
            | git credential fill >/dev/null 2>"$TMPDIR/credential.err"; then
            echo "credential fill produced credentials without a gh login" >&2
            exit 1
          fi
          if ! grep -q 'told us to quit' "$TMPDIR/credential.err"; then
            echo "credential exchange did not end; git looked elsewhere:" >&2
            cat "$TMPDIR/credential.err" >&2
            exit 1
          fi

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
